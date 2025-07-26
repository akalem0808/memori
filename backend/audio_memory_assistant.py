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

class AudioMemoryAssistant:
    def __init__(self, db_path="./memory_db", openai_api_key=None, memory_processor=None):
        """Initialize the Audio Memory Assistant with all required models"""
        
        # Core models
        print("Loading Whisper model...")
        self.whisper_model = whisper.load_model("base")
        
        print("Loading text embeddings...")
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        
        print("Loading emotion analyzer...")
        self.emotion_analyzer = pipeline(
            "text-classification", 
            model="j-hartmann/emotion-english-distilroberta-base",
            device=0 if torch.cuda.is_available() else -1
        )
        
        print("Initializing BERTopic...")
        self.topic_model = BERTopic(
            embedding_model="all-MiniLM-L6-v2",
            min_topic_size=3,
            calculate_probabilities=True
        )
        
        # Database setup
        self.db_path = f"{db_path}/metadata.db"
        self._init_sql_db()
        
        # Store memory processor reference
        self.memory_processor = memory_processor
        
        # Topics fitted flag
        self.topics_fitted = False
        
        print("Audio Memory Assistant initialized successfully!")
    
    def _init_sql_db(self):
        """Initialize SQLite database for metadata with multimodal support"""
        import os
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else '.', exist_ok=True)
        
        self.sql_conn = sqlite3.connect(self.db_path, check_same_thread=False)
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
    
    def process_audio_file(self, audio_file_path, metadata=None):
        """Process an audio file and store it in memory"""
        
        print(f"Processing audio file: {audio_file_path}")
        start_time = time.time()
        
        # 1. Transcribe audio
        print("Transcribing audio...")
        result = self.whisper_model.transcribe(audio_file_path)
        text = result["text"].strip()
        
        if not text:
            print("No speech detected in audio file")
            return None
        
        # 2. Analyze emotion
        print("Analyzing emotion...")
        emotion_result = self.emotion_analyzer(text)[0]
        emotion_label = emotion_result["label"]
        emotion_score = emotion_result["score"]
        
        # 3. Generate embedding
        print("Generating embedding...")
        embedding = self.embedder.encode(text)
        
        # 4. Extract topics (simplified for demo)
        topic_ids = []
        try:
            if hasattr(self, 'topic_model'):
                # Simple topic extraction
                topics, _ = self.topic_model.fit_transform([text])
                topic_ids = [int(topics[0])] if topics else []
        except Exception as e:
            print(f"Topic modeling failed: {e}")
            topic_ids = []
        
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
        
        # 6. Store in SQL database for backup
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
        
        # 7. Store in main memory system if available
        if self.memory_processor:
            self.memory_processor.store_memory(memory)
        
        processing_time = time.time() - start_time
        print(f"Audio processed successfully in {processing_time:.2f}s")
        print(f"Emotion: {emotion_label} ({emotion_score:.3f})")
        print(f"Text preview: {text[:100]}...")
        
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
        if hasattr(self, 'sql_conn'):
            self.sql_conn.close()

# Example usage
if __name__ == "__main__":
    assistant = AudioMemoryAssistant()
    
    # Example processing
    # result = assistant.process_audio_file("test_audio.wav")
    # print(f"Processed: {result}")
    
    assistant.close()
