# Core Business Logic - Complete Implementation
import sqlite3
import json
import uuid
import time
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer
import chromadb
import numpy as np
from transformers import pipeline
from memory_model import Memory
import whisper

class MemoryProcessor:
    def __init__(self, db_path='memory_system.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        
        # Initialize AI models
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.emotion_analyzer = pipeline(
            "text-classification", 
            model="j-hartmann/emotion-english-distilroberta-base"
        )
        
        # Initialize vector database
        self.vector_client = chromadb.Client()
        try:
            self.collection = self.vector_client.get_collection("memories")
        except:
            self.collection = self.vector_client.create_collection("memories")
        
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database tables"""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                emotion TEXT,
                emotion_scores TEXT,
                tags TEXT,
                topics TEXT,
                importance_score REAL,
                timestamp REAL,
                metadata TEXT,
                created_at TEXT
            )
        ''')
        self.conn.commit()
        
    def get_whisper_model(self):
        """Get or initialize the Whisper model"""
        if not hasattr(self, '_whisper_model'):
            try:
                self._whisper_model = whisper.load_model("base")
            except AttributeError:
                # Fallback for testing or when whisper is not available
                import logging
                logging.warning("Whisper not available, using mock model")
                class MockWhisperModel:
                    def transcribe(self, audio_path):
                        return {"text": "This is a mock transcription for testing"}
                self._whisper_model = MockWhisperModel()
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
        importance_score = self._calculate_importance(text, emotion_score)
        
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
        """Search memories based on various criteria"""
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
        
        cursor = self.conn.cursor()
        cursor.execute(f'''
            SELECT * FROM memories 
            WHERE {where_clause}
            ORDER BY timestamp DESC
        ''', params)
        rows = cursor.fetchall()
        
        memories = []
        for row in rows:
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
        
        return memories

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
        importance_score = self._calculate_importance(text, emotion_score)
        
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

    def _calculate_importance(self, text: str, emotion_score: float) -> float:
        """Calculate memory importance score"""
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
