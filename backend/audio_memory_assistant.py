# backend/audio_memory_assistant.py
"""
Audio Memory Assistant - Core audio processing component
Integrates with the multimodal memory system
"""

import whisper
import chromadb
from sentence_transformers import SentenceTransformer
from transformers import pipeline
from bertopic import BERTopic
import sqlite3
from datetime import datetime, timedelta
import numpy as np
import json
import uuid
import time
import logging
import torch
from typing import List
from memory_model import Memory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration constants to replace hardcoded model names
MODEL_CONFIG = {
    'WHISPER_MODEL': 'base',
    'EMBEDDING_MODEL': 'all-MiniLM-L6-v2',
    'EMOTION_MODEL': 'j-hartmann/emotion-english-distilroberta-base',
    'MIN_TOPIC_SIZE': 1,
    'DB_CONNECTION_TIMEOUT': 30.0,
    'MAX_RETRIES': 3
}

class AudioMemoryAssistant:
    def __init__(self, db_path="./memory_db", openai_api_key=None, memory_processor=None):
        """Initialize the Audio Memory Assistant with all required models"""
        
        # Initialize model attributes
        self.whisper_model = None
        self.embedder = None
        self.emotion_analyzer = None
        self.topic_model = None
        self.sql_conn = None
        
        # Core models with error handling
        try:
            logger.info("Loading Whisper model...")
            self.whisper_model = whisper.load_model(MODEL_CONFIG['WHISPER_MODEL'])
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise RuntimeError(f"Whisper model initialization failed: {e}")
        
        try:
            logger.info("Loading text embeddings...")
            self.embedder = SentenceTransformer(MODEL_CONFIG['EMBEDDING_MODEL'])
            logger.info("Text embeddings loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load text embeddings: {e}")
            raise RuntimeError(f"Text embeddings initialization failed: {e}")
        
        try:
            logger.info("Loading emotion analyzer...")
            self.emotion_analyzer = pipeline(
                "text-classification", 
                model=MODEL_CONFIG['EMOTION_MODEL'],
                device=0 if torch.cuda.is_available() else -1
            )
            logger.info("Emotion analyzer loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load emotion analyzer: {e}")
            raise RuntimeError(f"Emotion analyzer initialization failed: {e}")
        
        try:
            logger.info("Initializing BERTopic...")
            self.topic_model = BERTopic(
                embedding_model=MODEL_CONFIG['EMBEDDING_MODEL'],
                min_topic_size=MODEL_CONFIG['MIN_TOPIC_SIZE'],
                calculate_probabilities=True
            )
            logger.info("BERTopic initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize BERTopic: {e}")
            raise RuntimeError(f"BERTopic initialization failed: {e}")
        
        # Database setup with error handling
        self.db_path = f"{db_path}/metadata.db"
        try:
            self._init_sql_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise RuntimeError(f"Database initialization failed: {e}")
        
        # Store memory processor reference
        self.memory_processor = memory_processor
        
        # Topics fitted flag
        self.topics_fitted = False
        
        logger.info("Audio Memory Assistant initialized successfully!")
    
    def _init_sql_db(self):
        """Initialize SQLite database for metadata with multimodal support"""
        import os
        
        try:
            # Create directory if it doesn't exist
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            
            # Connect to database with timeout
            self.sql_conn = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=MODEL_CONFIG['DB_CONNECTION_TIMEOUT']
            )
            
            # Set WAL mode for better concurrency
            self.sql_conn.execute('PRAGMA journal_mode=WAL')
            
            # Create table with retry logic
            retries = 0
            while retries < MODEL_CONFIG['MAX_RETRIES']:
                try:
                    self.sql_conn.execute('''
                        CREATE TABLE IF NOT EXISTS memories (
                            id TEXT PRIMARY KEY,
                            timestamp REAL,
                            duration REAL,
                            text_content TEXT,
                            emotion_label TEXT,
                            emotion_score REAL,
                            topic_ids TEXT,
                            speaker_info TEXT,
                            file_path TEXT,
                            created_at TEXT,
                            movement_data TEXT,
                            context_data TEXT
                        )
                    ''')
                    self.sql_conn.commit()
                    break
                except sqlite3.OperationalError as e:
                    retries += 1
                    logger.warning(f"Database operation failed, retry {retries}/{MODEL_CONFIG['MAX_RETRIES']}: {e}")
                    if retries >= MODEL_CONFIG['MAX_RETRIES']:
                        raise
                    time.sleep(0.1 * retries)  # Exponential backoff
                    
        except Exception as e:
            logger.error(f"Failed to initialize SQLite database: {e}")
            if hasattr(self, 'sql_conn') and self.sql_conn:
                try:
                    self.sql_conn.close()
                except:
                    pass
                self.sql_conn = None
            raise
    
    def process_audio_file(self, audio_file_path, metadata=None):
        """Process an audio file and store it in memory"""
        
        logger.info(f"Processing audio file: {audio_file_path}")
        start_time = time.time()
        
        # Validate models are loaded
        if not self.whisper_model:
            logger.error("Whisper model not available")
            raise RuntimeError("Whisper model not initialized")
            
        if not self.emotion_analyzer:
            logger.error("Emotion analyzer not available")
            raise RuntimeError("Emotion analyzer not initialized")
            
        if not self.embedder:
            logger.error("Text embedder not available")
            raise RuntimeError("Text embedder not initialized")
        
        try:
            # 1. Transcribe audio
            logger.info("Transcribing audio...")
            result = self.whisper_model.transcribe(audio_file_path)
            text = result["text"].strip()
            
            if not text:
                logger.info("No speech detected in audio file")
                return None
            
            # 2. Analyze emotion
            logger.info("Analyzing emotion...")
            emotion_result = self.emotion_analyzer(text)[0]
            emotion_label = emotion_result["label"]
            emotion_score = emotion_result["score"]
            
            # 3. Generate embedding
            logger.info("Generating embedding...")
            embedding = self.embedder.encode(text)
            
            # 4. Extract topics (simplified for demo)
            topic_ids = []
            try:
                if self.topic_model:
                    # Simple topic extraction
                    topics, _ = self.topic_model.fit_transform([text])
                    
                    # Handle outlier topics (-1) by using the original text as a generic topic
                    if topics and topics[0] == -1:
                        # Extract a simple topic from the text itself (first few words or key phrase)
                        words = text.split()
                        simple_topic = " ".join(words[:3]) if len(words) > 3 else text[:20]
                        topic_ids = [simple_topic]
                    else:
                        topic_ids = [int(topics[0])] if topics else []
            except Exception as e:
                logger.error(f"Topic modeling failed: {e}")
                topic_ids = []
        
        except Exception as e:
            logger.error(f"Error processing audio file {audio_file_path}: {e}")
            raise RuntimeError(f"Audio processing failed: {e}")
        
        # 5. Create memory data structure
        memory_id = str(uuid.uuid4())
        timestamp = time.time()
        
        # Create enhanced memory structure for the multimodal system
        memory = Memory(
            id=memory_id,
            text=text,
            audio_text=text,
            timestamp=datetime.fromtimestamp(timestamp),
            emotion=emotion_label,
            emotion_scores={emotion_label: emotion_score},
            tags=self._generate_tags(text, emotion_label),
            topics=[str(t) for t in topic_ids],
            importance_score=self._calculate_importance(text, emotion_score),
            embedding=embedding.tolist(),
            enhanced_embedding=embedding.tolist(),
            source_type='audio',
            metadata=metadata or {},
            movement_data={
                'engagement_level': float(np.random.uniform(0.3, 0.9)),  # Simulated for demo
                'movement_intensity': float(np.random.uniform(0.1, 0.8)),
                'gesture_type': 'neutral',
                'body_language_summary': 'audio-only analysis, no visual data'
            },
            context_data={
                'environmental': {
                    'venue_type': metadata.get('location', 'unknown') if metadata else 'unknown',
                    'weather_conditions': 'unknown',
                    'room_temperature': 22.0
                },
                'biometric': {
                    'stress_score': self._estimate_stress_from_audio(emotion_label, emotion_score),
                    'heart_rate': 70,
                    'energy_level': float(np.random.uniform(0.4, 0.8))
                },
                'cognitive': {
                    'attention_level': float(np.random.uniform(0.5, 0.9)),
                    'focus_quality': float(np.random.uniform(0.4, 0.8))
                }
            },
            searchable_tags=self._generate_tags(text, emotion_label)
        )
        
        # 6. Store in SQL database for backup with error handling
        if self.sql_conn:
            try:
                retries = 0
                while retries < MODEL_CONFIG['MAX_RETRIES']:
                    try:
                        self.sql_conn.execute('''
                            INSERT OR REPLACE INTO memories 
                            (id, timestamp, duration, text_content, emotion_label, emotion_score, 
                             topic_ids, speaker_info, file_path, created_at, movement_data, context_data)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            memory_id, timestamp, result.get("duration", 0), text, 
                            emotion_label, emotion_score, json.dumps(topic_ids),
                            json.dumps(metadata) if metadata else None,
                            audio_file_path, datetime.now().isoformat(),
                            json.dumps(memory.movement_data if memory.movement_data else {}),
                            json.dumps(memory.context_data if memory.context_data else {})
                        ))
                        self.sql_conn.commit()
                        break
                    except sqlite3.OperationalError as e:
                        retries += 1
                        logger.warning(f"Database operation failed, retry {retries}/{MODEL_CONFIG['MAX_RETRIES']}: {e}")
                        if retries >= MODEL_CONFIG['MAX_RETRIES']:
                            logger.error(f"Failed to store memory in database after {MODEL_CONFIG['MAX_RETRIES']} retries")
                            break
                        time.sleep(0.1 * retries)  # Exponential backoff
            except Exception as e:
                logger.error(f"Database storage error: {e}")
        else:
            logger.warning("Database connection not available, memory not stored in SQL database")
        
        # 7. Store in main memory system if available
        try:
            if self.memory_processor:
                self.memory_processor.store_memory(memory)
                logger.info("Memory stored in main memory system")
        except Exception as e:
            logger.error(f"Failed to store memory in main system: {e}")
        
        processing_time = time.time() - start_time
        logger.info(f"Audio processed successfully in {processing_time:.2f}s")
        logger.info(f"Emotion: {emotion_label} ({emotion_score:.3f})")
        logger.info(f"Text preview: {text[:100]}...")
        
        return memory
    
    def _estimate_stress_from_audio(self, emotion: str, confidence: float) -> float:
        """Estimate stress level from audio emotion analysis"""
        stress_mapping = {
            'anger': 0.8,
            'fear': 0.9,
            'sadness': 0.6,
            'surprise': 0.4,
            'joy': 0.2,
            'neutral': 0.3
        }
        base_stress = stress_mapping.get(emotion, 0.5)
        # Adjust based on confidence - high confidence in negative emotions = higher stress
        if emotion in ['anger', 'fear', 'sadness']:
            return min(base_stress + (confidence - 0.5) * 0.3, 1.0)
        else:
            return max(base_stress - (confidence - 0.5) * 0.2, 0.0)
    
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
    
    def _generate_tags(self, text: str, emotion: str) -> List[str]:
        """Generate searchable tags"""
        tags = [emotion]
        
        text_lower = text.lower()
        
        # Topic tags
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
    
    def close(self):
        """Clean up resources"""
        if hasattr(self, 'sql_conn') and self.sql_conn:
            try:
                self.sql_conn.close()
                logger.info("Database connection closed successfully")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
            finally:
                self.sql_conn = None

# Example usage
if __name__ == "__main__":
    assistant = AudioMemoryAssistant()
    
    # Example processing
    # result = assistant.process_audio_file("test_audio.wav")
    # print(f"Processed: {result}")
    
    assistant.close()
