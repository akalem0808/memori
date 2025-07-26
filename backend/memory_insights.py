# Memory Insights Engine - Advanced implementation
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import numpy as np
from collections import Counter
from memory_model import Memory
import logging

logger = logging.getLogger(__name__)

class InsightEngine:
    """Advanced engine for generating insights from memory patterns"""
    
    def __init__(self):
        """Initialize the insight engine"""
        self.insight_generators = [
            self._check_emotion_patterns,
            self._check_topic_patterns,
            self._check_time_patterns,
            self._check_significance_patterns,
            self._check_memory_gaps
        ]
    
    def generate_insights(self, memories: List[Memory], user_preferences: Optional[Dict] = None) -> List[Dict]:
        """Generate insights from a list of memories"""
        if not memories:
            return []
            
        insights = []
        
        # Run all insight generators
        for generator in self.insight_generators:
            try:
                new_insights = generator(memories, user_preferences)
                if new_insights:
                    insights.extend(new_insights)
            except Exception as e:
                logger.error(f"Error in insight generator {generator.__name__}: {e}")
        
        # Sort by importance and confidence
        insights.sort(key=lambda x: (
            self._importance_to_value(x.get('importance', 'low')),
            x.get('confidence', 0)
        ), reverse=True)
        
        return insights
    
    def _importance_to_value(self, importance: str) -> int:
        """Convert importance string to numeric value for sorting"""
        values = {
            'critical': 4,
            'high': 3, 
            'medium': 2, 
            'low': 1
        }
        return values.get(importance.lower(), 0)
    
    def _check_emotion_patterns(self, memories: List[Memory], user_preferences: Optional[Dict] = None) -> List[Dict]:
        """Check for patterns in emotional states"""
        insights = []
        
        # Skip if too few memories
        if len(memories) < 3:
            return insights
            
        # Sort by timestamp
        sorted_memories = sorted(memories, key=lambda m: m.timestamp)
        
        # Check for consistent emotions
        emotions = [m.emotion for m in sorted_memories[-5:] if m.emotion]
        if len(emotions) >= 3:
            emotion_counts = Counter(emotions)
            most_common = emotion_counts.most_common(1)[0]
            
            # If same emotion appears frequently
            if most_common[1] >= 3 and most_common[1] / len(emotions) >= 0.6:
                insights.append({
                    'insight_type': 'pattern',
                    'title': f"Consistent {most_common[0]} detected",
                    'description': f"Your recent memories show consistent {most_common[0]} emotion.",
                    'confidence': 0.7 + (most_common[1] / len(emotions) * 0.3),  # Higher confidence with more matches
                    'importance': 'medium',
                    'suggested_actions': [
                        'Review related memories',
                        'Reflect on current emotional state'
                    ],
                    'data_points': [
                        {'id': m.id, 'text': m.text[:50], 'timestamp': m.timestamp.isoformat()}
                        for m in sorted_memories[-5:] if m.emotion == most_common[0]
                    ]
                })
        
        # Check for emotional shifts
        if len(emotions) >= 4:
            # Check if emotions shifted from one to another
            first_half = emotions[:len(emotions)//2]
            second_half = emotions[len(emotions)//2:]
            
            first_common = Counter(first_half).most_common(1)[0][0] if first_half else None
            second_common = Counter(second_half).most_common(1)[0][0] if second_half else None
            
            if first_common and second_common and first_common != second_common:
                insights.append({
                    'insight_type': 'shift',
                    'title': f"Emotional shift detected",
                    'description': f"Your emotions appear to have shifted from {first_common} to {second_common}.",
                    'confidence': 0.65,
                    'importance': 'medium',
                    'suggested_actions': [
                        'Compare earlier and recent memories',
                        'Reflect on recent life changes'
                    ],
                    'data_points': [
                        {'id': m.id, 'emotion': m.emotion, 'timestamp': m.timestamp.isoformat()}
                        for m in sorted_memories[-6:]
                    ]
                })
                
        return insights
    
    def _check_topic_patterns(self, memories: List[Memory], user_preferences: Optional[Dict] = None) -> List[Dict]:
        """Check for patterns in memory topics"""
        insights = []
        
        # Get memories with topics
        memories_with_topics = [m for m in memories if m.topics and len(m.topics) > 0]
        
        # Skip if too few memories with topics
        if len(memories_with_topics) < 3:
            return insights
            
        # Extract all topics
        all_topics = []
        for memory in memories_with_topics:
            all_topics.extend(memory.topics)
            
        # Find most common topics
        topic_counts = Counter(all_topics).most_common(3)
        
        # If a topic appears frequently
        if topic_counts and topic_counts[0][1] >= 3:
            dominant_topic = topic_counts[0][0]
            related_memories = [m for m in memories_with_topics if dominant_topic in m.topics]
            
            insights.append({
                'insight_type': 'topic_focus',
                'title': f"Frequent topic: {dominant_topic}",
                'description': f"This topic appears in {topic_counts[0][1]} of your recent memories.",
                'confidence': 0.8,
                'importance': 'medium',
                'suggested_actions': [
                    'Explore memories with this topic',
                    'Reflect on why this topic is recurring'
                ],
                'data_points': [
                    {'id': m.id, 'text': m.text[:50], 'timestamp': m.timestamp.isoformat()}
                    for m in related_memories[:5]
                ]
            })
            
        # Check for topic co-occurrence
        if len(topic_counts) >= 2:
            # Find memories that contain both top topics
            top_topics = [t[0] for t in topic_counts[:2]]
            co_occurring_memories = [
                m for m in memories_with_topics 
                if top_topics[0] in m.topics and top_topics[1] in m.topics
            ]
            
            if len(co_occurring_memories) >= 2:
                insights.append({
                    'insight_type': 'topic_connection',
                    'title': f"Connected topics: {top_topics[0]} and {top_topics[1]}",
                    'description': f"These topics frequently appear together in your memories.",
                    'confidence': 0.7,
                    'importance': 'low',
                    'suggested_actions': [
                        'Explore the connection between these topics',
                        'Review memories containing both topics'
                    ],
                    'data_points': [
                        {'id': m.id, 'text': m.text[:50], 'timestamp': m.timestamp.isoformat()}
                        for m in co_occurring_memories[:3]
                    ]
                })
        
        return insights
    
    def _check_time_patterns(self, memories: List[Memory], user_preferences: Optional[Dict] = None) -> List[Dict]:
        """Check for patterns in memory timing"""
        insights = []
        
        # Skip if too few memories
        if len(memories) < 5:
            return insights
            
        # Sort by timestamp
        sorted_memories = sorted(memories, key=lambda m: m.timestamp)
        
        # Extract hours of day
        hours = [m.timestamp.hour for m in sorted_memories if hasattr(m.timestamp, 'hour')]
        
        if len(hours) >= 5:
            hour_counts = Counter(hours)
            
            # Check for time of day patterns
            morning_count = sum(hour_counts.get(h, 0) for h in range(5, 12))
            afternoon_count = sum(hour_counts.get(h, 0) for h in range(12, 18))
            evening_count = sum(hour_counts.get(h, 0) for h in range(18, 24))
            night_count = sum(hour_counts.get(h, 0) for h in range(0, 5))
            
            time_counts = [
                ("morning", morning_count),
                ("afternoon", afternoon_count),
                ("evening", evening_count),
                ("night", night_count)
            ]
            
            dominant_time = max(time_counts, key=lambda x: x[1])
            
            # If there's a clear pattern in time of day
            if dominant_time[1] > len(hours) * 0.5:
                insights.append({
                    'insight_type': 'time_pattern',
                    'title': f"{dominant_time[0].capitalize()} activity pattern",
                    'description': f"Most of your memories occur during the {dominant_time[0]}.",
                    'confidence': 0.7,
                    'importance': 'low',
                    'suggested_actions': [
                        'Consider why this time period is significant',
                        'Explore memories from other times of day'
                    ]
                })
        
        # Check for memory frequency changes
        if len(sorted_memories) >= 10:
            half_point = len(sorted_memories) // 2
            first_half = sorted_memories[:half_point]
            second_half = sorted_memories[half_point:]
            
            first_timespan = (first_half[-1].timestamp - first_half[0].timestamp).total_seconds()
            second_timespan = (second_half[-1].timestamp - second_half[0].timestamp).total_seconds()
            
            # Normalize by number of memories
            first_freq = first_timespan / len(first_half) if first_timespan > 0 else 0
            second_freq = second_timespan / len(second_half) if second_timespan > 0 else 0
            
            # If frequency changed significantly
            if first_freq > 0 and second_freq > 0 and (first_freq / second_freq > 2 or second_freq / first_freq > 2):
                change_type = "increased" if second_freq < first_freq else "decreased"
                
                insights.append({
                    'insight_type': 'frequency_change',
                    'title': f"Memory frequency has {change_type}",
                    'description': f"You're creating memories at a {change_type} rate recently.",
                    'confidence': 0.6,
                    'importance': 'medium',
                    'suggested_actions': [
                        'Reflect on recent lifestyle changes',
                        'Consider what might be affecting your memory recording'
                    ]
                })
        
        return insights
    
    def _check_significance_patterns(self, memories: List[Memory], user_preferences: Optional[Dict] = None) -> List[Dict]:
        """Check for patterns in memory significance/importance"""
        insights = []
        
        # Get memories with importance scores
        memories_with_importance = [m for m in memories if m.importance_score is not None]
        
        # Skip if too few memories
        if len(memories_with_importance) < 5:
            return insights
            
        # Sort by timestamp
        sorted_memories = sorted(memories_with_importance, key=lambda m: m.timestamp)
        
        # Calculate average importance
        importance_scores = [m.importance_score for m in sorted_memories]
        avg_importance = sum(importance_scores) / len(importance_scores)
        
        # Find highly significant memories
        significant_memories = [m for m in sorted_memories if m.importance_score > 0.7]
        
        if len(significant_memories) >= 2:
            insights.append({
                'insight_type': 'significant_memories',
                'title': "Highly significant memories detected",
                'description': f"You have {len(significant_memories)} memories that stand out as particularly important.",
                'confidence': 0.75,
                'importance': 'high',
                'suggested_actions': [
                    'Review these significant memories',
                    'Consider creating a highlight collection'
                ],
                'data_points': [
                    {'id': m.id, 'text': m.text[:50], 'importance': m.importance_score, 'timestamp': m.timestamp.isoformat()}
                    for m in significant_memories[:3]
                ]
            })
            
        # Check for change in memory significance
        if len(sorted_memories) >= 10:
            half_point = len(sorted_memories) // 2
            first_half = sorted_memories[:half_point]
            second_half = sorted_memories[half_point:]
            
            first_avg = sum(m.importance_score for m in first_half) / len(first_half)
            second_avg = sum(m.importance_score for m in second_half) / len(second_half)
            
            # If significance changed notably
            if abs(first_avg - second_avg) > 0.2:
                change_type = "increased" if second_avg > first_avg else "decreased"
                
                insights.append({
                    'insight_type': 'significance_change',
                    'title': f"Memory significance has {change_type}",
                    'description': f"Your recent memories have {change_type} in importance.",
                    'confidence': 0.65,
                    'importance': 'medium',
                    'suggested_actions': [
                        'Reflect on factors affecting memory significance',
                        'Consider what life changes might be influencing memory importance'
                    ]
                })
        
        return insights
    
    def _check_memory_gaps(self, memories: List[Memory], user_preferences: Optional[Dict] = None) -> List[Dict]:
        """Identify significant gaps in memory recording"""
        insights = []
        
        # Skip if too few memories
        if len(memories) < 5:
            return insights
            
        # Sort by timestamp
        sorted_memories = sorted(memories, key=lambda m: m.timestamp)
        
        # Calculate time gaps between consecutive memories
        gaps = []
        for i in range(1, len(sorted_memories)):
            gap = (sorted_memories[i].timestamp - sorted_memories[i-1].timestamp).total_seconds() / 3600  # hours
            gaps.append((i-1, i, gap))
            
        # Calculate average and standard deviation of gaps
        avg_gap = sum(g[2] for g in gaps) / len(gaps)
        std_gap = np.std([g[2] for g in gaps])
        
        # Find unusual gaps (> 2 standard deviations from mean)
        unusual_gaps = [g for g in gaps if g[2] > avg_gap + 2 * std_gap and g[2] > 48]  # At least 48 hours
        
        if unusual_gaps:
            # Get the largest gap
            largest_gap = max(unusual_gaps, key=lambda g: g[2])
            start_mem = sorted_memories[largest_gap[0]]
            end_mem = sorted_memories[largest_gap[1]]
            gap_days = largest_gap[2] / 24  # Convert to days
            
            insights.append({
                'insight_type': 'memory_gap',
                'title': f"Significant memory gap detected",
                'description': f"There's a {gap_days:.1f} day gap between memories from {start_mem.timestamp.strftime('%b %d')} to {end_mem.timestamp.strftime('%b %d')}.",
                'confidence': 0.8,
                'importance': 'medium' if gap_days > 7 else 'low',
                'suggested_actions': [
                    'Reflect on what happened during this period',
                    'Consider if there are memories you want to record from this time'
                ],
                'data_points': [
                    {'id': start_mem.id, 'text': start_mem.text[:50], 'timestamp': start_mem.timestamp.isoformat()},
                    {'id': end_mem.id, 'text': end_mem.text[:50], 'timestamp': end_mem.timestamp.isoformat()}
                ]
            })
        
        return insights
