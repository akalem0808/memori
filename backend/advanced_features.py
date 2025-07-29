# advanced_features.py
"""
Advanced features and extensions for the memory system
Including real-time processing, smart notifications, and AI insights
"""

import asyncio
import json
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
import logging
from pathlib import Path
import threading
from memory_model import Memory
import queue
import time
import tempfile
import os
from memory_utils import MemoryProcessor, MemoryFilter

# Configuration constants to replace magic numbers
CONFIG = {
    'DEFAULT_MAX_QUEUE_SIZE': 1000,
    'DEFAULT_QUEUE_TIMEOUT': 1.0,
    'AUDIO_BUFFER_STALE_TIMEOUT': 5.0,
    'MAX_AUDIO_BUFFER_SIZE': 10,
    'MAX_CONSECUTIVE_ERRORS': 5,
    'ERROR_PAUSE_DURATION': 1.0,
    'THREAD_JOIN_TIMEOUT': 5.0,
    'HIGH_STRESS_THRESHOLD': 0.7,
    'HIGH_ENGAGEMENT_THRESHOLD': 0.8,
    'LOW_ENGAGEMENT_THRESHOLD': 0.3,
    'INSIGHT_TIME_PERIOD_DAYS': 7,
    'RECENT_MEMORIES_LIMIT': 50,
    'TOP_INSIGHTS_LIMIT': 10,
    'STRESS_ALERT_MEMORY_COUNT': 5
}

logger = logging.getLogger(__name__)

@dataclass
class MemoryInsight:
    """AI-generated insights about memory patterns"""
    insight_type: str  # pattern, recommendation, warning, achievement
    title: str
    description: str
    confidence: float
    importance: str  # low, medium, high, critical
    suggested_actions: List[str]
    data_points: List[Dict]
    created_at: datetime

@dataclass
class MemoryNotification:
    """Smart notifications based on memory analysis"""
    notification_id: str
    type: str  # reminder, pattern_alert, goal_progress, insight
    title: str
    message: str
    priority: str  # low, medium, high, urgent
    scheduled_time: datetime
    memory_ids: List[str]
    actions: List[Dict]  # [{"action": "view_memories", "label": "View Details"}]

class RealTimeMemoryProcessor:
    """Real-time memory processing with streaming analysis"""
    
    def __init__(self, memory_processor: MemoryProcessor, max_queue_size: Optional[int] = None):
        self.memory_processor = memory_processor
        max_queue_size = max_queue_size or CONFIG['DEFAULT_MAX_QUEUE_SIZE']
        self.processing_queue = queue.Queue(maxsize=max_queue_size)  # Bounded queue
        self.subscribers = []
        self.subscribers_lock = threading.Lock()  # Thread-safe subscriber list
        self.is_running = False
        self.worker_thread = None
        self._shutdown_event = threading.Event()  # Clean shutdown signaling
        
    def subscribe(self, callback: Callable[[Dict], None]):
        """Subscribe to real-time memory events (thread-safe)"""
        with self.subscribers_lock:
            self.subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable[[Dict], None]):
        """Unsubscribe from real-time memory events (thread-safe)"""
        with self.subscribers_lock:
            if callback in self.subscribers:
                self.subscribers.remove(callback)
    
    def start_processing(self):
        """Start real-time processing thread"""
        if self.is_running:
            return
            
        self.is_running = True
        self._shutdown_event.clear()
        self.worker_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.worker_thread.start()
        logger.info("Real-time memory processing started")
    
    def stop_processing(self, timeout: Optional[float] = None):
        """Stop real-time processing with proper cleanup"""
        if not self.is_running:
            return
            
        timeout = timeout or CONFIG['THREAD_JOIN_TIMEOUT']
        self.is_running = False
        self._shutdown_event.set()
        
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=timeout)
            if self.worker_thread.is_alive():
                logger.warning("Worker thread did not shut down gracefully")
        
        # Clear remaining queue items
        try:
            while True:
                self.processing_queue.get_nowait()
                self.processing_queue.task_done()
        except queue.Empty:
            pass
            
        logger.info("Real-time memory processing stopped")
    
    def queue_memory(self, memory_data: Dict, timeout: float = 1.0):
        """Queue a memory for real-time processing with backpressure handling"""
        try:
            self.processing_queue.put({
                'type': 'memory',
                'data': memory_data,
                'timestamp': time.time()
            }, timeout=timeout)
        except queue.Full:
            logger.warning("Processing queue is full, dropping memory data")
            return False
        return True
    
    def queue_audio_chunk(self, audio_chunk: bytes, metadata: Dict, timeout: float = 0.5):
        """Queue an audio chunk for streaming analysis with backpressure handling"""
        try:
            self.processing_queue.put({
                'type': 'audio_chunk',
                'data': audio_chunk,
                'metadata': metadata,
                'timestamp': time.time()
            }, timeout=timeout)
        except queue.Full:
            logger.warning("Processing queue is full, dropping audio chunk")
            return False
        return True
    
    def _process_loop(self):
        """Main processing loop with enhanced error handling"""
        # Store audio chunks for streaming transcription
        audio_buffer = []
        last_chunk_time = 0
        consecutive_errors = 0
        
        logger.info("Processing loop started")
        
        while self.is_running and not self._shutdown_event.is_set():
            try:
                # Process items from queue with timeout
                try:
                    item = self.processing_queue.get(timeout=CONFIG['DEFAULT_QUEUE_TIMEOUT'])
                    consecutive_errors = 0  # Reset error counter on successful get
                except queue.Empty:
                    # Process any remaining audio chunks if buffer is getting stale
                    if audio_buffer and (time.time() - last_chunk_time > CONFIG['AUDIO_BUFFER_STALE_TIMEOUT']):
                        logger.debug("Processing stale audio buffer")
                        self._process_audio_buffer(audio_buffer)
                        audio_buffer = []
                    continue
                
                # Validate item structure
                if not isinstance(item, dict) or 'type' not in item:
                    logger.error("Invalid item structure in queue")
                    self.processing_queue.task_done()
                    continue
                
                # Handle different item types
                if item['type'] == 'memory':
                    # Process complete memory
                    if 'data' in item:
                        self._process_memory_data(item['data'])
                    else:
                        logger.error("Memory item missing data field")
                    
                elif item['type'] == 'audio_chunk':
                    # Validate audio chunk
                    if 'data' not in item or 'metadata' not in item:
                        logger.error("Audio chunk missing required fields")
                        self.processing_queue.task_done()
                        continue
                        
                    # Add to audio buffer
                    audio_buffer.append(item)
                    last_chunk_time = time.time()
                    
                    # Process buffer if it's getting large
                    if len(audio_buffer) >= CONFIG['MAX_AUDIO_BUFFER_SIZE']:
                        logger.debug(f"Processing audio buffer with {len(audio_buffer)} chunks")
                        self._process_audio_buffer(audio_buffer)
                        audio_buffer = []
                else:
                    logger.warning(f"Unknown item type: {item['type']}")
                
                # Mark as done
                self.processing_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in real-time processing: {e}")
                consecutive_errors += 1
                
                # If too many consecutive errors, pause briefly
                if consecutive_errors >= CONFIG['MAX_CONSECUTIVE_ERRORS']:
                    logger.error(f"Too many consecutive errors ({consecutive_errors}), pausing processing")
                    time.sleep(CONFIG['ERROR_PAUSE_DURATION'])
                    consecutive_errors = 0
        
        # Process any remaining audio buffer before shutdown
        if audio_buffer:
            logger.info("Processing remaining audio buffer before shutdown")
            self._process_audio_buffer(audio_buffer)
            
        logger.info("Processing loop ended")
                
    def _process_memory_data(self, memory_data: Dict):
        """Process complete memory data with thread safety"""
        try:
            # Convert dict to Memory object if needed
            if not isinstance(memory_data, Memory):
                memory = Memory(**memory_data)
            else:
                memory = memory_data
                
            # Generate real-time insights
            insights = self._generate_insights([memory])
            
            # Generate real-time analysis
            analysis = self._analyze_realtime_data(memory) if hasattr(self, '_analyze_realtime_data') else {}
            
            # Notify subscribers with thread safety
            event_data = {
                'event_type': 'new_memory',
                'memory_id': memory.id,
                'insights': insights,
                'analysis': analysis,
                'timestamp': time.time()
            }
            
            # Get thread-safe copy of subscribers
            with self.subscribers_lock:
                subscribers_copy = self.subscribers.copy()
            
            for callback in subscribers_copy:
                try:
                    callback(event_data)
                except Exception as e:
                    logger.error(f"Error in subscriber callback: {e}")
                    
            logger.info(f"Processed memory: {memory.id}")
            return memory.id
        except Exception as e:
            logger.error(f"Error processing memory data: {e}")
            return None
    
    def _process_audio_buffer(self, audio_chunks: List[Dict]):
        """Process a buffer of audio chunks with enhanced error handling"""
        temp_path = None
        try:
            if not audio_chunks:
                return
                
            # Validate audio chunks
            for chunk in audio_chunks:
                if not isinstance(chunk.get('data'), bytes):
                    logger.error("Invalid audio chunk data type")
                    return
                if not chunk.get('metadata'):
                    logger.warning("Audio chunk missing metadata")
                    
            # Concatenate audio data
            try:
                audio_data = b''.join([chunk['data'] for chunk in audio_chunks])
            except (KeyError, TypeError) as e:
                logger.error(f"Failed to concatenate audio data: {e}")
                return
                
            if len(audio_data) == 0:
                logger.warning("Empty audio data after concatenation")
                return
                
            metadata = audio_chunks[-1]['metadata']  # Use latest metadata
            
            # Determine suffix from metadata or use default
            format_hint = metadata.get('format', 'wav').lower()
            # Validate format
            valid_formats = ['wav', 'mp3', 'flac', 'm4a', 'ogg']
            if format_hint not in valid_formats:
                logger.warning(f"Unknown audio format '{format_hint}', using wav")
                format_hint = 'wav'
            suffix = f'.{format_hint}'
            
            # Create a temporary file with proper error handling
            try:
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
                    temp_path = temp_file.name
                    temp_file.write(audio_data)
            except (OSError, IOError) as e:
                logger.error(f"Failed to create temporary audio file: {e}")
                return
            
            try:
                # Use memory processor to transcribe with error handling
                whisper_model = self.memory_processor.get_whisper_model()
                if not whisper_model:
                    logger.error("Whisper model not available")
                    return
                    
                result = whisper_model.transcribe(temp_path)
                text = result.get("text", "").strip()
                
                if not text:
                    logger.info("No speech detected in audio buffer")
                    return
                
                # Analyze emotion in streaming mode with error handling
                emotion_analyzer = self.memory_processor.get_emotion_analyzer()
                if not emotion_analyzer:
                    logger.error("Emotion analyzer not available")
                    return
                    
                emotion_result = emotion_analyzer(text)[0]
                emotion = emotion_result.get("label", "neutral")
                emotion_score = emotion_result.get("score", 0.5)
                
                # Create a streaming event
                stream_event = {
                    'event_type': 'streaming_transcription',
                    'text': text,
                    'emotion': emotion,
                    'emotion_score': emotion_score,
                    'metadata': metadata,
                    'timestamp': time.time()
                }
                
                # Notify subscribers with thread safety
                with self.subscribers_lock:
                    subscribers_copy = self.subscribers.copy()
                    
                for callback in subscribers_copy:
                    try:
                        callback(stream_event)
                    except Exception as e:
                        logger.error(f"Error in subscriber callback: {e}")
                
                logger.info(f"Processed audio buffer: {len(text)} chars")
                
            except Exception as e:
                logger.error(f"Error during audio transcription/analysis: {e}")
                
        except Exception as e:
            logger.error(f"Error processing audio buffer: {e}")
        finally:
            # Guaranteed temp file cleanup
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    logger.debug(f"Cleaned up temp file: {temp_path}")
                except OSError as e:
                    logger.error(f"Failed to cleanup temp file {temp_path}: {e}")
    
    def _generate_insights(self, memories: List[Memory]) -> List[Dict]:
        """Generate insights from memories"""
        # Use the comprehensive insight engine if available
        try:
            from memory_insights import InsightEngine
            insight_engine = InsightEngine()
            return insight_engine.generate_insights(memories)
        except ImportError:
            # Fallback to simple implementation
            insights = []
            
            # Skip if no memories
            if not memories:
                return insights
                
            try:
                # Example: Check for emotional patterns
                emotions = [m.emotion for m in memories if m.emotion]
                if len(emotions) >= 3:
                    # Check if the same emotion repeats
                    if len(set(emotions[-3:])) == 1:
                        insights.append({
                            'insight_type': 'pattern',
                            'title': f"Consistent {emotions[-1]} detected",
                            'description': f"Your last three memories show consistent {emotions[-1]} emotion.",
                            'confidence': 0.8,
                            'importance': 'medium',
                            'suggested_actions': [
                                'Review related memories',
                                'Consider journaling about this pattern'
                            ]
                        })
                
                # More sophisticated insights can be added here
            except Exception as e:
                logger.error(f"Error generating insights: {e}")
                
            return insights
            
    def _analyze_realtime_data(self, memory_data: Memory) -> Dict[str, Any]:
        """Real-time analysis of memory data"""
        analysis = {
            'patterns_detected': [],
            'anomalies': [],
            'recommendations': []
        }
        # Detect engagement patterns
        engagement = memory_data.movement_data.get('engagement_level', 0.5) if memory_data.movement_data else 0.5
        if engagement > 0.8:
            analysis['patterns_detected'].append('high_engagement')
        elif engagement < 0.3:
            analysis['patterns_detected'].append('low_engagement')
        # Detect stress patterns
        stress = memory_data.context_data.get('biometric', {}).get('stress_score', 0.5) if memory_data.context_data else 0.5
        if stress > 0.7:
            analysis['anomalies'].append('high_stress_detected')
            analysis['recommendations'].append('consider_break_or_relaxation')
        # Detect emotion-body language mismatches
        emotion = memory_data.emotion
        movement_intensity = memory_data.movement_data.get('movement_intensity', 0.5) if memory_data.movement_data else 0.5
        if emotion == 'joy' and movement_intensity < 0.3:
            analysis['anomalies'].append('emotion_movement_mismatch')
        return analysis

class SmartInsightEngine:
    """AI-powered insight generation from memory patterns"""
    
    def __init__(self, memory_processor: MemoryProcessor):
        self.memory_processor = memory_processor
        self.insight_history = []
    
    def generate_insights(self, time_period: int = 7) -> List[MemoryInsight]:
        """Generate AI insights from recent memories"""
        insights = []
        
        # Get recent memories
        end_date = datetime.now()
        start_date = end_date - timedelta(days=time_period)
        
        # Get memories within date range
        memories = self.memory_processor.get_memories(
            start_date=start_date,
            end_date=end_date
        )
        
        if not memories:
            return insights
        
        # Pattern analysis
        insights.extend(self._analyze_engagement_patterns(memories))
        insights.extend(self._analyze_stress_patterns(memories))
        insights.extend(self._analyze_location_performance(memories))
        insights.extend(self._analyze_temporal_patterns(memories))
        insights.extend(self._analyze_emotion_trends(memories))
        
        # Filter and rank insights
        insights = self._rank_insights(insights)
        
        return insights[:10]  # Return top 10 insights
    
    def _analyze_engagement_patterns(self, memories: List[Memory]) -> List[MemoryInsight]:
        """Analyze engagement level patterns"""
        insights = []
        
        # Calculate engagement by location
        location_engagement = {}
        for memory in memories:
            location = memory.context_data.get('environmental', {}).get('venue_type', 'unknown') if memory.context_data else 'unknown'
            engagement = memory.movement_data.get('engagement_level', 0.5) if memory.movement_data else 0.5
            
            if location not in location_engagement:
                location_engagement[location] = []
            location_engagement[location].append(engagement)
        
        # Find best location for engagement
        location_averages = {
            loc: np.mean(engagements) 
            for loc, engagements in location_engagement.items()
            if len(engagements) >= 3  # Minimum samples
        }
        
        if location_averages:
            best_location = max(location_averages.items(), key=lambda x: x[1])
            worst_location = min(location_averages.items(), key=lambda x: x[1])
            
            if best_location[1] - worst_location[1] > 0.2:  # Significant difference
                insights.append(MemoryInsight(
                    insight_type="pattern",
                    title="Location Impact on Engagement",
                    description=f"Your engagement is {(best_location[1] - worst_location[1]) * 100:.1f}% higher in {best_location[0]} compared to {worst_location[0]}",
                    confidence=0.8,
                    importance="medium",
                    suggested_actions=[
                        f"Schedule important meetings in {best_location[0]}",
                        f"Minimize complex discussions in {worst_location[0]}",
                        "Consider environmental factors that differ between locations"
                    ],
                    data_points=[
                        {"location": loc, "avg_engagement": avg}
                        for loc, avg in location_averages.items()
                    ],
                    created_at=datetime.now()
                ))
        
        return insights
    
    def _analyze_stress_patterns(self, memories: List[Memory]) -> List[MemoryInsight]:
        """Analyze stress level patterns"""
        insights = []
        
        # Analyze stress by time of day
        hourly_stress = {}
        for memory in memories:
            hour = memory.timestamp.hour
            stress = memory.context_data.get('biometric', {}).get('stress_score', 0.5) if memory.context_data else 0.5
            
            if hour not in hourly_stress:
                hourly_stress[hour] = []
            hourly_stress[hour].append(stress)
        
        # Find peak stress hours
        hourly_averages = {
            hour: np.mean(stresses)
            for hour, stresses in hourly_stress.items()
            if len(stresses) >= 2
        }
        
        if hourly_averages:
            peak_stress_hour = max(hourly_averages.items(), key=lambda x: x[1])
            low_stress_hour = min(hourly_averages.items(), key=lambda x: x[1])
            
            if peak_stress_hour[1] > 0.6:  # High stress threshold
                insights.append(MemoryInsight(
                    insight_type="warning",
                    title="Peak Stress Time Detected",
                    description=f"Your stress levels peak around {peak_stress_hour[0]:02d}:00 ({peak_stress_hour[1]*100:.1f}% average stress)",
                    confidence=0.7,
                    importance="high",
                    suggested_actions=[
                        f"Schedule breaks before {peak_stress_hour[0]:02d}:00",
                        "Avoid scheduling important decisions during high-stress hours",
                        f"Consider moving stressful tasks to {low_stress_hour[0]:02d}:00 when stress is lower"
                    ],
                    data_points=[
                        {"hour": hour, "avg_stress": avg}
                        for hour, avg in hourly_averages.items()
                    ],
                    created_at=datetime.now()
                ))
        
        return insights
    
    def _analyze_location_performance(self, memories: List[Memory]) -> List[MemoryInsight]:
        """Analyze location-based performance"""
        insights = []
        
        # Analyze importance scores by location
        location_importance = {}
        for memory in memories:
            location = memory.context_data.get('environmental', {}).get('venue_type', 'unknown') if memory.context_data else 'unknown'
            importance = memory.importance_score
            
            if location not in location_importance:
                location_importance[location] = []
            location_importance[location].append(importance)
        
        # Find most productive locations
        location_averages = {
            loc: np.mean(scores)
            for loc, scores in location_importance.items()
            if len(scores) >= 3
        }
        
        if location_averages:
            best_location = max(location_averages.items(), key=lambda x: x[1])
            
            if best_location[1] > 0.7:  # High importance threshold
                insights.append(MemoryInsight(
                    insight_type="recommendation",
                    title="High-Value Location Identified",
                    description=f"Your most important conversations happen in {best_location[0]} (importance score: {best_location[1]*100:.1f}%)",
                    confidence=0.8,
                    importance="medium",
                    suggested_actions=[
                        f"Schedule key meetings in {best_location[0]}",
                        "Analyze what makes this location effective",
                        "Replicate successful environmental factors in other spaces"
                    ],
                    data_points=[
                        {"location": loc, "avg_importance": avg}
                        for loc, avg in location_averages.items()
                    ],
                    created_at=datetime.now()
                ))
        
        return insights
    
    def _analyze_temporal_patterns(self, memories: List[Memory]) -> List[MemoryInsight]:
        """Analyze time-based patterns"""
        insights = []
        
        # Analyze engagement trends over time
        daily_engagement = {}
        for memory in memories:
            date = memory.timestamp.date()
            engagement = memory.movement_data.get('engagement_level', 0.5) if memory.movement_data else 0.5
            
            if date not in daily_engagement:
                daily_engagement[date] = []
            daily_engagement[date].append(engagement)
        
        # Calculate daily averages
        daily_averages = {
            date: np.mean(engagements)
            for date, engagements in daily_engagement.items()
        }
        
        if len(daily_averages) >= 5:  # Need enough data points
            dates = sorted(daily_averages.keys())
            values = [daily_averages[date] for date in dates]
            
            # Simple trend analysis
            recent_avg = np.mean(values[-3:])  # Last 3 days
            earlier_avg = np.mean(values[:-3])  # Earlier days
            
            if recent_avg > earlier_avg + 0.1:  # Positive trend
                insights.append(MemoryInsight(
                    insight_type="achievement",
                    title="Engagement Improvement Detected",
                    description=f"Your engagement has improved by {(recent_avg - earlier_avg)*100:.1f}% over recent days",
                    confidence=0.7,
                    importance="medium",
                    suggested_actions=[
                        "Identify what changed in recent days",
                        "Continue current practices",
                        "Document successful strategies"
                    ],
                    data_points=[
                        {"date": str(date), "engagement": daily_averages[date]}
                        for date in dates[-7:]  # Last week
                    ],
                    created_at=datetime.now()
                ))
        
        return insights
    
    def _analyze_emotion_trends(self, memories: List[Memory]) -> List[MemoryInsight]:
        """Analyze emotion trends"""
        insights = []
        
        # Count emotions
        emotion_counts = {}
        total_memories = len(memories)
        
        for memory in memories:
            emotion = memory.emotion
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        
        # Find dominant emotion
        if emotion_counts:
            dominant_emotion = max(emotion_counts.items(), key=lambda x: x[1])
            percentage = (dominant_emotion[1] / total_memories) * 100
            
            if percentage > 40:  # Dominant emotion threshold
                if dominant_emotion[0] in ['joy', 'surprise']:
                    insight_type = "achievement"
                    importance = "medium"
                elif dominant_emotion[0] in ['sadness', 'anger', 'fear']:
                    insight_type = "warning"
                    importance = "high"
                else:
                    insight_type = "pattern"
                    importance = "low"
                
                insights.append(MemoryInsight(
                    insight_type=insight_type,
                    title=f"Dominant Emotion: {dominant_emotion[0].title()}",
                    description=f"{percentage:.1f}% of your recent conversations show {dominant_emotion[0]} emotion",
                    confidence=0.8,
                    importance=importance,
                    suggested_actions=[
                        "Reflect on factors contributing to this emotional pattern",
                        "Consider whether this aligns with your goals",
                        "Explore strategies to maintain positive emotions" if dominant_emotion[0] == 'joy' else "Consider techniques to improve emotional well-being"
                    ],
                    data_points=[
                        {"emotion": emotion, "count": count, "percentage": (count/total_memories)*100}
                        for emotion, count in emotion_counts.items()
                    ],
                    created_at=datetime.now()
                ))
        
        return insights
    
    def _rank_insights(self, insights: List[MemoryInsight]) -> List[MemoryInsight]:
        """Rank insights by importance and relevance"""
        
        importance_weights = {
            'critical': 1.0,
            'high': 0.8,
            'medium': 0.6,
            'low': 0.4
        }
        
        type_weights = {
            'warning': 1.0,
            'achievement': 0.9,
            'recommendation': 0.8,
            'pattern': 0.7
        }
        
        def calculate_score(insight):
            importance_score = importance_weights.get(insight.importance, 0.5)
            type_score = type_weights.get(insight.insight_type, 0.5)
            confidence_score = insight.confidence
            
            return importance_score * type_score * confidence_score
        
        insights.sort(key=calculate_score, reverse=True)
        return insights

class SmartNotificationSystem:
    """Intelligent notification system based on memory patterns"""
    
    def __init__(self, memory_processor: MemoryProcessor, insight_engine: SmartInsightEngine):
        self.memory_processor = memory_processor
        self.insight_engine = insight_engine
        self.notification_queue = []
        self.user_preferences = {
            'max_daily_notifications': 5,
            'quiet_hours': (22, 7),  # 10 PM to 7 AM
            'notification_types': ['insight', 'pattern_alert', 'goal_progress'],
            'priority_threshold': 'medium'
        }
    
    def generate_smart_notifications(self) -> List[MemoryNotification]:
        """Generate intelligent notifications based on insights and patterns"""
        notifications = []
        
        # Get recent insights
        insights = self.insight_engine.generate_insights(time_period=7)
        
        # Convert high-priority insights to notifications
        for insight in insights:
            if insight.importance in ['high', 'critical']:
                notification = self._insight_to_notification(insight)
                notifications.append(notification)
        
        # Check for pattern-based notifications
        pattern_notifications = self._check_pattern_alerts()
        notifications.extend(pattern_notifications)
        
        # Check for goal progress notifications
        goal_notifications = self._check_goal_progress()
        notifications.extend(goal_notifications)
        
        # Filter and prioritize
        notifications = self._filter_notifications(notifications)
        
        return notifications
    
    def _insight_to_notification(self, insight: MemoryInsight) -> MemoryNotification:
        """Convert an insight to a notification"""
        
        return MemoryNotification(
            notification_id=f"insight_{int(time.time())}",
            type="insight",
            title=insight.title,
            message=insight.description,
            priority=insight.importance,
            scheduled_time=datetime.now() + timedelta(minutes=5),
            memory_ids=[],  # Populated based on insight data
            actions=[
                {"action": "view_insight", "label": "View Details"},
                {"action": "dismiss", "label": "Dismiss"}
            ]
        )
    
    def _check_pattern_alerts(self) -> List[MemoryNotification]:
        """Check for pattern-based alerts"""
        notifications = []
        
        # Check for unusual stress patterns
        recent_memories = self.memory_processor.get_memories(
            start_date=datetime.now() - timedelta(days=1),
            limit=50
        )
        
        if recent_memories:
            avg_stress = np.mean([
                m.context_data.get('biometric', {}).get('stress_score', 0.5) if m.context_data else 0.5
                for m in recent_memories
            ])
            
            if avg_stress > CONFIG['HIGH_STRESS_THRESHOLD']:  # High stress day
                notifications.append(MemoryNotification(
                    notification_id=f"stress_alert_{int(time.time())}",
                    type="pattern_alert",
                    title="High Stress Day Detected",
                    message=f"Your stress levels have been elevated today (avg: {avg_stress*100:.0f}%). Consider taking a break.",
                    priority="high",
                    scheduled_time=datetime.now(),
                    memory_ids=[m.id for m in recent_memories[-CONFIG['STRESS_ALERT_MEMORY_COUNT']:]],
                    actions=[
                        {"action": "view_stress_memories", "label": "View Details"},
                        {"action": "schedule_break", "label": "Schedule Break"},
                        {"action": "dismiss", "label": "Dismiss"}
                    ]
                ))
        
        return notifications
    
    def _check_goal_progress(self) -> List[MemoryNotification]:
        """Check progress toward user goals"""
        notifications = []
        
        # Example: Engagement improvement goal
        week_memories = self.memory_processor.get_memories(
            start_date=datetime.now() - timedelta(days=7),
            limit=100
        )
        
        if len(week_memories) >= 10:
            avg_engagement = np.mean([
                m.movement_data.get('engagement_level', 0.5) if m.movement_data else 0.5
                for m in week_memories
            ])
            if avg_engagement > 0.75:  # High engagement week
                notifications.append(MemoryNotification(
                    notification_id=f"goal_progress_{int(time.time())}",
                    type="goal_progress",
                    title="Great Engagement This Week! 🎉",
                    message=f"You've maintained {avg_engagement*100:.0f}% average engagement. Keep it up!",
                    priority="medium",
                    scheduled_time=datetime.now(),
                    memory_ids=[m.id for m in week_memories if m.movement_data and m.movement_data.get('engagement_level', 0.0) > 0.8],
                    actions=[
                        {"action": "view_high_engagement", "label": "View Best Moments"},
                        {"action": "share_achievement", "label": "Share Progress"},
                        {"action": "dismiss", "label": "Thanks!"}
                    ]
                ))
        
        return notifications
    
    def _filter_notifications(self, notifications: List[MemoryNotification]) -> List[MemoryNotification]:
        """Filter notifications based on user preferences"""
        
        # Filter by enabled types
        notifications = [
            n for n in notifications 
            if n.type in self.user_preferences['notification_types']
        ]
        
        # Filter by priority threshold
        priority_order = {'low': 0, 'medium': 1, 'high': 2, 'urgent': 3}
        threshold = priority_order[self.user_preferences['priority_threshold']]
        
        notifications = [
            n for n in notifications
            if priority_order.get(n.priority, 0) >= threshold
        ]
        
        # Limit daily notifications
        notifications = notifications[:self.user_preferences['max_daily_notifications']]
        
        # Check quiet hours
        current_hour = datetime.now().hour
        quiet_start, quiet_end = self.user_preferences['quiet_hours']
        
        if quiet_start <= current_hour or current_hour <= quiet_end:
            # During quiet hours, only show urgent notifications
            notifications = [n for n in notifications if n.priority == 'urgent']
        
        return notifications

# Example usage and integration
async def main():
    """Example of how to use the advanced features"""
    
    # Initialize components
    memory_processor = MemoryProcessor()
    insight_engine = SmartInsightEngine(memory_processor)
    notification_system = SmartNotificationSystem(memory_processor, insight_engine)
    
    # Start real-time processing
    realtime_processor = RealTimeMemoryProcessor(memory_processor)
    
    # Subscribe to real-time events
    def handle_memory_event(event):
        print(f"New memory processed: {event['memory_id']}")
        print(f"Analysis: {event['analysis']}")
    
    realtime_processor.subscribe(handle_memory_event)
    realtime_processor.start_processing()
    
    try:
        # Generate insights
        print("Generating insights...")
        insights = insight_engine.generate_insights()
        
        for insight in insights[:3]:  # Show top 3
            print(f"\n{insight.insight_type.upper()}: {insight.title}")
            print(f"Description: {insight.description}")
            print(f"Importance: {insight.importance}")
            print(f"Actions: {', '.join(insight.suggested_actions)}")
        
        # Generate notifications
        print("\nGenerating notifications...")
        notifications = notification_system.generate_smart_notifications()
        
        for notification in notifications:
            print(f"\n{notification.type.upper()}: {notification.title}")
            print(f"Message: {notification.message}")
            print(f"Priority: {notification.priority}")
        
        # Simulate real-time processing
        print("\nSimulating real-time processing...")
        await asyncio.sleep(2)
        
    finally:
        realtime_processor.stop_processing()

if __name__ == "__main__":
    asyncio.run(main())
