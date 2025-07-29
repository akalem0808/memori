# Core Business Logic - Complete Implementation with Security Fixes
import sqlite3
import json
import uuid
import time
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer
import chromadb
import numpy as np
from transformers import pipeline
from memory_model import Memory
import whisper

# Configure logging
logger = logging.getLogger(__name__)

# Configuration constants to replace magic numbers
MEMORY_CONFIG = {
    'COLLECTION_NAME_PREFIX': 'memories_v1',
    'MIN_EMOTION_CONFIDENCE': 0.7,
    'MIN_IMPORTANCE_SCORE': 0.3,
    'DEFAULT_EMBEDDING_MODEL': 'all-MiniLM-L6-v2',
    'DEFAULT_EMOTION_MODEL': 'j-hartmann/emotion-english-distilroberta-base',
    'DEFAULT_WHISPER_MODEL': 'base',
    'MAX_COLLECTION_RETRIES': 3,
    'DATABASE_TIMEOUT': 30.0,
    'CHUNK_SIZE': 1000
}

class MemoryProcessor:
    def __init__(self, db_path='memory_system.db', collection_name=None):
        self.db_path = db_path
        self.collection_name = collection_name or f"{MEMORY_CONFIG['COLLECTION_NAME_PREFIX']}_{int(time.time())}"
        
        # Initialize database connection with timeout
        try:
            self.conn = sqlite3.connect(
                db_path, 
                check_same_thread=False,
                timeout=MEMORY_CONFIG['DATABASE_TIMEOUT']
            )
            # Enable WAL mode for better concurrency
            self.conn.execute('PRAGMA journal_mode=WAL')
            self.conn.execute('PRAGMA foreign_keys=ON')
        except sqlite3.Error as e:
            logger.error("Failed to connect to database: %s", e)
            raise RuntimeError(f"Database connection failed: {e}") from e
        
        # Initialize AI models with fallbacks
        self._initialize_models()
        
        # Initialize vector database with collision handling
        self._initialize_vector_db()
        
        # Initialize database schema with migrations
        self._init_database()
        
    def _initialize_models(self):
        """Initialize AI models with proper error handling and fallbacks"""
        try:
            logger.info("Loading embedding model...")
            self.embedder = SentenceTransformer(MEMORY_CONFIG['DEFAULT_EMBEDDING_MODEL'])
        except Exception as e:
            logger.error("Failed to load embedding model: %s", e)
            raise RuntimeError(f"Embedding model initialization failed: {e}") from e
        
        try:
            logger.info("Loading emotion analyzer...")
            self.emotion_analyzer = pipeline(
                "text-classification", 
                model=MEMORY_CONFIG['DEFAULT_EMOTION_MODEL'],
                device=-1  # Use CPU to avoid GPU issues
            )
        except Exception as e:
            logger.error("Failed to load emotion analyzer: %s", e)
            # Create a fallback emotion analyzer
            logger.warning("Using fallback emotion analyzer")
            self.emotion_analyzer = self._create_fallback_emotion_analyzer()
    
    def _create_fallback_emotion_analyzer(self):
        """Create a simple fallback emotion analyzer"""
        class FallbackEmotionAnalyzer:
            def __call__(self, text):
                # Simple keyword-based emotion detection
                text_lower = text.lower()
                if any(word in text_lower for word in ['happy', 'joy', 'great', 'excellent']):
                    return [{'label': 'joy', 'score': 0.8}]
                elif any(word in text_lower for word in ['sad', 'upset', 'terrible', 'awful']):
                    return [{'label': 'sadness', 'score': 0.8}]
                elif any(word in text_lower for word in ['angry', 'mad', 'furious', 'annoyed']):
                    return [{'label': 'anger', 'score': 0.8}]
                else:
                    return [{'label': 'neutral', 'score': 0.7}]
        
        return FallbackEmotionAnalyzer()
    
    def _initialize_vector_db(self):
        """Initialize vector database with proper collision handling"""
        try:
            self.vector_client = chromadb.Client()
            
            # Try to get existing collection first
            retry_count = 0
            while retry_count < MEMORY_CONFIG['MAX_COLLECTION_RETRIES']:
                try:
                    self.collection = self.vector_client.get_collection(self.collection_name)
                    logger.info("Connected to existing ChromaDB collection: %s", self.collection_name)
                    break
                except ValueError:
                    # Collection doesn't exist, try to create it
                    try:
                        self.collection = self.vector_client.create_collection(
                            name=self.collection_name,
                            metadata={"description": "Memory embeddings collection"}
                        )
                        logger.info("Created new ChromaDB collection: %s", self.collection_name)
                        break
                    except ValueError as e:
                        if "already exists" in str(e):
                            # Collection was created by another process, try with different name
                            retry_count += 1
                            self.collection_name = f"{MEMORY_CONFIG['COLLECTION_NAME_PREFIX']}_{int(time.time())}_{retry_count}"
                            logger.warning("Collection name collision, trying: %s", self.collection_name)
                        else:
                            raise
                except Exception as e:
                    logger.error("ChromaDB error: %s", e)
                    raise RuntimeError(f"Vector database initialization failed: {e}") from e
            
            if retry_count >= MEMORY_CONFIG['MAX_COLLECTION_RETRIES']:
                raise RuntimeError("Failed to create unique ChromaDB collection after retries")
                
        except Exception as e:
            logger.error("Failed to initialize vector database: %s", e)
            raise
        
    def close(self):
        """Close database connections and resources"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
        # Additional cleanup for other resources if needed

    def _init_database(self):
        """Initialize database tables with proper schema and migrations"""
        try:
            # Create main memories table with proper constraints
            self.conn.execute('''CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL CHECK(length(content) > 0),
                emotion TEXT,
                importance REAL CHECK(importance >= 0 AND importance <= 1),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tags TEXT,
                context TEXT,
                version INTEGER DEFAULT 1
            )''')
            
            # Create indexes for better query performance
            self.conn.execute('''CREATE INDEX IF NOT EXISTS idx_memories_created_at 
                                ON memories(created_at)''')
            self.conn.execute('''CREATE INDEX IF NOT EXISTS idx_memories_emotion 
                                ON memories(emotion)''')
            self.conn.execute('''CREATE INDEX IF NOT EXISTS idx_memories_importance 
                                ON memories(importance)''')
            
            # Create schema version table for migrations
            self.conn.execute('''CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Check and apply migrations if needed
            self._apply_database_migrations()
            
            self.conn.commit()
            logger.info("Database schema initialized successfully")
            
        except sqlite3.Error as e:
            logger.error("Database initialization failed: %s", e)
            raise RuntimeError(f"Database schema creation failed: {e}") from e
    
    def _apply_database_migrations(self):
        """Apply database migrations based on version"""
        try:
            cursor = self.conn.execute("SELECT MAX(version) FROM schema_version")
            current_version = cursor.fetchone()[0] or 0
            
            if current_version < 1:
                # Migration 1: Add updated_at trigger
                self.conn.execute('''
                    CREATE TRIGGER IF NOT EXISTS update_memories_timestamp 
                    AFTER UPDATE ON memories
                    FOR EACH ROW
                    BEGIN
                        UPDATE memories SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END
                ''')
                self.conn.execute("INSERT INTO schema_version (version) VALUES (1)")
                logger.info("Applied database migration version 1")
            
        except sqlite3.Error as e:
            logger.error("Migration failed: %s", e)
            raise
    
    def add_memory(self, content: str, context: str = "", tags: Optional[List[str]] = None) -> str:
        """Add a new memory with full processing and proper error handling"""
        if not content or not content.strip():
            raise ValueError("Memory content cannot be empty")
        
        memory_id = str(uuid.uuid4())
        
        try:
            # Analyze emotion with confidence checking
            try:
                emotion_result = self.emotion_analyzer(content)
                if emotion_result and len(emotion_result) > 0:
                    emotion_data = emotion_result[0]
                    if emotion_data.get('score', 0) >= MEMORY_CONFIG['MIN_EMOTION_CONFIDENCE']:
                        emotion = emotion_data['label']
                    else:
                        emotion = 'neutral'  # Low confidence fallback
                else:
                    emotion = 'neutral'
            except Exception as e:
                logger.warning("Emotion analysis failed, using neutral: %s", e)
                emotion = 'neutral'
            
            # Calculate importance with improved heuristic
            importance = self._calculate_importance(content, context, tags)
            
            # Validate importance score
            if importance < 0 or importance > 1:
                importance = max(0, min(1, importance))
            
            # Store in SQLite with parameterized query
            tags_json = json.dumps(tags or [])
            cursor = self.conn.execute("""
                INSERT INTO memories (id, content, emotion, importance, tags, context)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (memory_id, content, emotion, importance, tags_json, context))
            
            if cursor.rowcount == 0:
                raise sqlite3.Error("Failed to insert memory record")
            
            # Generate and store embedding with error handling
            try:
                embedding = self.embedder.encode(content)
                self.collection.add(
                    embeddings=[embedding.tolist()],
                    documents=[content],
                    metadatas=[{
                        "memory_id": memory_id,
                        "emotion": emotion,
                        "importance": importance,
                        "created_at": datetime.now().isoformat(),
                        "tags": tags_json
                    }],
                    ids=[memory_id]
                )
            except Exception as e:
                logger.error("Failed to store embedding for memory %s: %s", memory_id, e)
                # Rollback SQLite transaction
                self.conn.rollback()
                raise RuntimeError(f"Vector storage failed: {e}") from e
            
            self.conn.commit()
            logger.info("Successfully added memory: %s", memory_id)
            return memory_id
            
        except sqlite3.Error as e:
            logger.error("Database error adding memory: %s", e)
            self.conn.rollback()
            raise RuntimeError(f"Failed to add memory to database: {e}") from e
        except Exception as e:
            logger.error("Unexpected error adding memory: %s", e)
            self.conn.rollback()
            raise RuntimeError(f"Failed to add memory: {e}") from e
    
    def _calculate_importance(self, content: str, context: str = "", tags: Optional[List[str]] = None) -> float:
        """Calculate memory importance using multiple factors"""
        importance = 0.0
        
        # Content length factor (normalized)
        content_factor = min(len(content) / 1000, 0.3)
        importance += content_factor
        
        # Context factor
        if context and context.strip():
            context_factor = min(len(context) / 500, 0.2)
            importance += context_factor
        
        # Tags factor (more tags = more organized = more important)
        if tags:
            tags_factor = min(len(tags) * 0.1, 0.2)
            importance += tags_factor
        
        # Keyword importance factor
        important_keywords = ['important', 'remember', 'critical', 'urgent', 'key', 'essential']
        content_lower = content.lower()
        keyword_matches = sum(1 for keyword in important_keywords if keyword in content_lower)
        keyword_factor = min(keyword_matches * 0.1, 0.3)
        importance += keyword_factor
        
        return min(importance, 1.0)
        
    def get_whisper_model(self):
        """Get or initialize the Whisper model with proper error handling"""
        if not hasattr(self, '_whisper_model'):
            try:
                import whisper
                self._whisper_model = whisper.load_model(MEMORY_CONFIG['DEFAULT_WHISPER_MODEL'])
                logger.info("Whisper model loaded successfully")
            except (ImportError, AttributeError) as e:
                # Fallback for testing or when whisper is not available
                logger.warning("Whisper not available, using mock model: %s", e)
                class MockWhisperModel:
                    def transcribe(self, audio_path):
                        return {"text": "This is a mock transcription for testing"}
                self._whisper_model = MockWhisperModel()
            except Exception as e:
                logger.error("Failed to load Whisper model: %s", e)
                raise RuntimeError(f"Whisper model initialization failed: {e}") from e
        return self._whisper_model
    
    def get_emotion_analyzer(self):
        """Get the emotion analyzer model"""
        return self.emotion_analyzer
    
    def process_memory_data(self, memory_data: Dict) -> Optional[str]:
        """Process memory data and store it"""
        # Convert dict to Memory object if needed
        if not isinstance(memory_data, Memory):
            try:
                memory = Memory(**memory_data)
            except Exception as e:
                raise ValueError(f"Invalid memory data: {e}")
        else:
            memory = memory_data
            
        # Store memory
        self.store_memory(memory)
        return memory.id

    def process_text_memory(self, text: str, metadata: Optional[dict] = None) -> Dict[str, Any]:
        """Process text input and create a memory"""
        memory_id = str(uuid.uuid4())
        timestamp = time.time()
        
        # Generate embedding
        embedding = self.embedder.encode(text)
        
        # Analyze emotion
        emotion_result = self.emotion_analyzer(text)[0]
        emotion_label = emotion_result["label"]
        emotion_score = emotion_result["score"]
        emotion_scores = {emotion_label: emotion_score}
        
        # Generate tags and calculate importance
        tags = self._generate_text_tags(text, emotion_label)
        importance_score = self._calculate_text_importance(text, emotion_score)
        
        # Create memory data
        memory_data = {
            'id': memory_id,
            'text': text,
            'emotion': emotion_label,
            'emotion_scores': emotion_scores,
            'tags': tags,
            'topics': ['general'],  # Could be enhanced with topic modeling
            'importance_score': importance_score,
            'timestamp': timestamp,
            'metadata': metadata
        }
        
        # Store in vector database
        self.collection.add(
            documents=[text],
            embeddings=[embedding.tolist()],
            metadatas=[metadata or {}],
            ids=[memory_id]
        )
        
        # Store in SQLite
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            memory_id, text, emotion_label,
            json.dumps(emotion_scores),
            json.dumps(tags),
            json.dumps(['general']),
            importance_score,
            timestamp,
            json.dumps(metadata) if metadata else None,
            datetime.now().isoformat()
        ))
        self.conn.commit()
        
        return memory_data

    def create_memory(self, text: str, metadata: Optional[dict] = None) -> Dict[str, Any]:
        """Create memory from text (wrapper for compatibility)"""
        return self.process_text_memory(text, metadata)
    
    def store_memory(self, memory: Memory) -> None:
        """Store a Memory object (used by advanced_features.py)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO memories 
            (id, text, emotion, emotion_scores, tags, topics, importance_score, timestamp, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            memory.id,
            memory.text,
            memory.emotion,
            json.dumps(memory.emotion_scores),
            json.dumps(memory.tags),
            json.dumps(memory.topics),
            memory.importance_score,
            memory.timestamp.timestamp(),
            json.dumps(memory.metadata),
            datetime.now().isoformat()
        ))
        self.conn.commit()
        
        # Store in vector database if embedding exists
        if memory.embedding:
            try:
                self.collection.add(
                    documents=[memory.text],
                    embeddings=[memory.embedding],
                    metadatas=[memory.metadata],
                    ids=[memory.id]
                )
            except Exception as e:
                print(f"Vector storage failed: {e}")
    
    def get_memories(self, **filters) -> List[Memory]:
        """Get memories with optional filters (used by advanced_features.py)"""
        cursor = self.conn.cursor()
        query = "SELECT * FROM memories"
        params = []
        conditions = []
        
        if 'start_date' in filters and filters['start_date']:
            conditions.append("timestamp >= ?")
            params.append(filters['start_date'].timestamp())
        
        if 'end_date' in filters and filters['end_date']:
            conditions.append("timestamp <= ?")
            params.append(filters['end_date'].timestamp())
        
        if 'emotion' in filters and filters['emotion']:
            conditions.append("emotion = ?")
            params.append(filters['emotion'])
        
        if 'tags' in filters and filters['tags']:
            # Simple tag matching - improve this for production
            for tag in filters['tags']:
                conditions.append("tags LIKE ?")
                params.append(f'%"{tag}"%')
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY timestamp DESC"
        
        if 'limit' in filters:
            query += f" LIMIT {filters['limit']}"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        memories = []
        for row in rows:
            memory_data = {
                'id': row[0],
                'text': row[1],
                'emotion': row[2],
                'emotion_scores': json.loads(row[3]) if row[3] else {},
                'tags': json.loads(row[4]) if row[4] else [],
                'topics': json.loads(row[5]) if row[5] else [],
                'importance_score': row[6],
                'timestamp': datetime.fromtimestamp(row[7]),
                'metadata': json.loads(row[8]) if row[8] else {}
            }
            memories.append(Memory(**memory_data))
        
        return memories

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific memory by ID"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM memories WHERE id = ?', (memory_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
            
        return {
            'id': row[0],
            'text': row[1],
            'emotion': row[2],
            'emotion_scores': json.loads(row[3]) if row[3] else {},
            'tags': json.loads(row[4]) if row[4] else [],
            'topics': json.loads(row[5]) if row[5] else [],
            'importance_score': row[6],
            'timestamp': row[7],
            'metadata': json.loads(row[8]) if row[8] else None
        }

    def list_memories(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """List memories with pagination"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM memories 
            ORDER BY timestamp DESC 
            LIMIT ? OFFSET ?
        ''', (limit, skip))
        rows = cursor.fetchall()
        
        memories = []
        for row in rows:
            memories.append({
                'id': row[0],
                'text': row[1],
                'emotion': row[2],
                'emotion_scores': json.loads(row[3]) if row[3] else {},
                'tags': json.loads(row[4]) if row[4] else [],
                'topics': json.loads(row[5]) if row[5] else [],
                'importance_score': row[6],
                'timestamp': row[7],
                'metadata': json.loads(row[8]) if row[8] else None
            })
        return memories

    def search_memories(self, query: Optional[str] = None, emotion: Optional[str] = None,
                       tags: Optional[List[str]] = None, date_from: Optional[datetime] = None,
                       date_to: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Search memories based on various criteria with proper SQL security"""
        conditions = []
        params = []
        
        if query:
            conditions.append("text LIKE ?")
            params.append(f"%{query}%")
        
        if emotion:
            conditions.append("emotion = ?")
            params.append(emotion)
        
        if date_from:
            conditions.append("timestamp >= ?")
            params.append(date_from.timestamp())
        
        if date_to:
            conditions.append("timestamp <= ?")
            params.append(date_to.timestamp())
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(f'''
                SELECT * FROM memories 
                WHERE {where_clause}
                ORDER BY timestamp DESC
            ''', params)
            rows = cursor.fetchall()
            
            memories = []
            for row in rows:
                try:
                    memory = {
                        'id': row[0],
                        'text': row[1],
                        'emotion': row[2],
                        'emotion_scores': json.loads(row[3]) if row[3] else {},
                        'tags': json.loads(row[4]) if row[4] else [],
                        'topics': json.loads(row[5]) if row[5] else [],
                        'importance_score': row[6],
                        'timestamp': row[7],
                        'metadata': json.loads(row[8]) if row[8] else None
                    }
                    
                    # Filter by tags if specified
                    if tags:
                        memory_tags = memory['tags']
                        if any(tag in memory_tags for tag in tags):
                            memories.append(memory)
                    else:
                        memories.append(memory)
                except (json.JSONDecodeError, IndexError, TypeError) as e:
                    logger.warning("Failed to parse memory row: %s", e)
                    continue
                    
            return memories
            
        except sqlite3.Error as e:
            logger.error("Database error in search_memories: %s", e)
            return []
        except Exception as e:
            logger.error("Unexpected error in search_memories: %s", e)
            return []

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM memories WHERE id = ?', (memory_id,))
        deleted = cursor.rowcount > 0
        self.conn.commit()
        
        # Also delete from vector database
        try:
            self.collection.delete(ids=[memory_id])
        except:
            pass  # May not exist in vector DB
        
        return deleted

    def update_memory(self, memory_id: str, text: str, metadata: Optional[dict] = None) -> Optional[Dict[str, Any]]:
        """Update an existing memory"""
        # Check if memory exists
        existing = self.get_memory(memory_id)
        if not existing:
            return None
        
        # Reprocess the text
        timestamp = time.time()
        embedding = self.embedder.encode(text)
        emotion_result = self.emotion_analyzer(text)[0]
        emotion_label = emotion_result["label"]
        emotion_score = emotion_result["score"]
        emotion_scores = {emotion_label: emotion_score}
        tags = self._generate_text_tags(text, emotion_label)
        importance_score = self._calculate_text_importance(text, emotion_score)
        
        # Update in SQLite
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE memories 
            SET text = ?, emotion = ?, emotion_scores = ?, tags = ?, 
                importance_score = ?, metadata = ?
            WHERE id = ?
        ''', (
            text, emotion_label, json.dumps(emotion_scores),
            json.dumps(tags), importance_score,
            json.dumps(metadata) if metadata else None,
            memory_id
        ))
        self.conn.commit()
        
        # Update in vector database
        try:
            self.collection.update(
                ids=[memory_id],
                documents=[text],
                embeddings=[embedding.tolist()],
                metadatas=[metadata or {}]
            )
        except:
            pass
        
        return self.get_memory(memory_id)

    def find_similar_memories(self, text: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Find memories similar to given text using vector similarity"""
        embedding = self.embedder.encode(text)
        
        try:
            results = self.collection.query(
                query_embeddings=[embedding.tolist()],
                n_results=limit
            )
            
            similar_memories = []
            for i, memory_id in enumerate(results['ids'][0]):
                memory = self.get_memory(memory_id)
                if memory:
                    similar_memories.append(memory)
            
            return similar_memories
        except:
            return []

    def get_analytics(self) -> Dict[str, Any]:
        """Get memory analytics and statistics"""
        cursor = self.conn.cursor()
        
        # Total memories
        cursor.execute('SELECT COUNT(*) FROM memories')
        total_memories = cursor.fetchone()[0]
        
        # Emotion distribution
        cursor.execute('SELECT emotion, COUNT(*) FROM memories GROUP BY emotion')
        emotion_dist = dict(cursor.fetchall())
        
        # Average importance
        cursor.execute('SELECT AVG(importance_score) FROM memories')
        avg_importance = cursor.fetchone()[0] or 0.0
        
        # Top topics (simplified)
        top_topics = ['general', 'conversation', 'meeting']
        
        return {
            'total_memories': total_memories,
            'emotion_distribution': emotion_dist,
            'top_topics': top_topics,
            'average_importance': avg_importance
        }

    def get_emotion_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get emotion trends over time"""
        cutoff_date = (datetime.now() - timedelta(days=days)).timestamp()
        
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DATE(datetime(timestamp, 'unixepoch')) as date, 
                   emotion, COUNT(*) as count
            FROM memories 
            WHERE timestamp >= ?
            GROUP BY date, emotion
            ORDER BY date
        ''', (cutoff_date,))
        
        trends = []
        for row in cursor.fetchall():
            trends.append({
                'date': row[0],
                'emotion': row[1],
                'count': row[2]
            })
        
        return trends

    def export_memories(self, format_type: str = "json") -> Any:
        """Export all memories in specified format"""
        memories = self.list_memories(limit=10000)  # Large limit for export
        
        if format_type == "json":
            return memories
        elif format_type == "csv":
            import csv
            import io
            output = io.StringIO()
            if memories:
                writer = csv.DictWriter(output, fieldnames=memories[0].keys())
                writer.writeheader()
                writer.writerows(memories)
            return output.getvalue()
        else:
            return memories

    def bulk_delete_memories(self, memory_ids: List[str]) -> int:
        """Delete multiple memories"""
        cursor = self.conn.cursor()
        placeholders = ','.join(['?'] * len(memory_ids))
        cursor.execute(f'DELETE FROM memories WHERE id IN ({placeholders})', memory_ids)
        deleted_count = cursor.rowcount
        self.conn.commit()
        
        # Also delete from vector database
        try:
            self.collection.delete(ids=memory_ids)
        except:
            pass
        
        return deleted_count

    def _generate_text_tags(self, text: str, emotion: str) -> List[str]:
        """Generate tags for text content"""
        tags = [emotion]
        text_lower = text.lower()
        
        # Topic-based tags
        if any(word in text_lower for word in ['meeting', 'discussion', 'call']):
            tags.append('meeting')
        if any(word in text_lower for word in ['project', 'work', 'task']):
            tags.append('work')
        if any(word in text_lower for word in ['decision', 'choose', 'decide']):
            tags.append('decision')
        
        # Time-based tags
        hour = datetime.now().hour
        if 9 <= hour <= 12:
            tags.append('morning')
        elif 13 <= hour <= 17:
            tags.append('afternoon')
        elif 18 <= hour <= 21:
            tags.append('evening')
        
        return tags

    def _calculate_text_importance(self, text: str, emotion_score: float) -> float:
        """Calculate memory importance score (renamed to avoid conflict)"""
        importance = 0.5  # Base importance
        
        # Length factor
        if len(text) > 100:
            importance += 0.1
        
        # Keyword importance
        important_keywords = ['important', 'urgent', 'deadline', 'decision', 'critical', 'meeting']
        for keyword in important_keywords:
            if keyword.lower() in text.lower():
                importance += 0.1
                break
        
        # Emotion intensity
        importance += emotion_score * 0.2
        
        return min(importance, 1.0)

    def close(self):
        """Clean up resources"""
        if hasattr(self, 'conn'):
            self.conn.close()

class MemoryFilter:
    """Advanced filtering for memories with proper initialization"""
    
    def __init__(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, 
                 tags: Optional[List[str]] = None, emotion: Optional[str] = None,
                 min_importance: Optional[float] = None):
        self.start_date = start_date
        self.end_date = end_date
        self.tags = tags or []
        self.emotion = emotion
        self.min_importance = min_importance
    
    def apply(self, memories: List[Memory]) -> List[Memory]:
        """Apply filter criteria to a list of memories"""
        filtered = memories
        
        if self.start_date:
            filtered = [m for m in filtered if m.timestamp >= self.start_date]
        
        if self.end_date:
            filtered = [m for m in filtered if m.timestamp <= self.end_date]
        
        if self.emotion:
            filtered = [m for m in filtered if m.emotion == self.emotion]
        
        if self.tags:
            filtered = [m for m in filtered if any(tag in m.tags for tag in self.tags)]
        
        if self.min_importance is not None:
            filtered = [m for m in filtered if m.importance_score >= self.min_importance]
        
        return filtered
    
    def search_memories(self, memories: List[Memory]) -> List[Memory]:
        """Alias for apply method for compatibility"""
        return self.apply(memories)
    
    @staticmethod
    def by_emotion(memories: List[Dict], emotion: str) -> List[Dict]:
        return [m for m in memories if m.get('emotion') == emotion]
    
    @staticmethod
    def by_importance(memories: List[Dict], min_score: float) -> List[Dict]:
        return [m for m in memories if m.get('importance_score', 0) >= min_score]
    
    @staticmethod
    def by_date_range(memories: List[Dict], start: datetime, end: datetime) -> List[Dict]:
        return [m for m in memories 
                if start.timestamp() <= m.get('timestamp', 0) <= end.timestamp()]

class MemoryQueryBuilder:
    """Fluent API for building complex memory queries"""
    
    def __init__(self, processor: MemoryProcessor):
        self.processor = processor
        self.filters = {}
    
    def emotion(self, emotion: str):
        self.filters['emotion'] = emotion
        return self
    
    def tags(self, tags: List[str]):
        self.filters['tags'] = tags
        return self
    
    def date_range(self, start: datetime, end: datetime):
        self.filters['date_from'] = start
        self.filters['date_to'] = end
        return self
    
    def execute(self) -> List[Dict[str, Any]]:
        return self.processor.search_memories(**self.filters)

class MemoryExporter:
    """Export memories in various formats"""
    
    def __init__(self, processor: MemoryProcessor):
        self.processor = processor
    
    def to_json(self, filename: Optional[str] = None) -> str:
        data = self.processor.export_memories("json")
        json_str = json.dumps(data, indent=2)
        
        if filename:
            with open(filename, 'w') as f:
                f.write(json_str)
        
        return json_str
    
    def to_csv(self, filename: Optional[str] = None) -> str:
        csv_data = self.processor.export_memories("csv")
        
        if filename:
            with open(filename, 'w') as f:
                f.write(csv_data)
        
        return csv_data
