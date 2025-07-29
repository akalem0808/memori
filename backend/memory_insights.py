# Advanced Memory Insights Engine with Configuration Constants
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from dataclasses import dataclass
import statistics

# Configure logging
logger = logging.getLogger(__name__)

# Configuration constants replacing magic numbers
INSIGHTS_CONFIG = {
    'HIGH_ACTIVITY_THRESHOLD': 10,           # memories per day
    'LOW_ACTIVITY_THRESHOLD': 2,             # memories per day  
    'HIGH_IMPORTANCE_THRESHOLD': 0.8,        # importance score
    'MEDIUM_IMPORTANCE_THRESHOLD': 0.5,      # importance score
    'EMOTION_PATTERN_MIN_CONFIDENCE': 0.7,   # minimum confidence for pattern detection
    'TOPIC_CLUSTERING_MIN_SIZE': 3,          # minimum cluster size for topics
    'TREND_ANALYSIS_DAYS': 7,                # days for trend analysis
    'INSIGHT_CONFIDENCE_THRESHOLD': 0.6,     # minimum confidence for insights
    'MAX_INSIGHTS_PER_CATEGORY': 5,          # maximum insights per category
    'MEMORY_FRESHNESS_DAYS': 30,             # days for considering memories fresh
    'PATTERN_SIGNIFICANCE_THRESHOLD': 0.05,  # statistical significance threshold
    'MIN_SAMPLE_SIZE': 5,                    # minimum sample size for statistics
    'OUTLIER_DETECTION_THRESHOLD': 2.0,      # standard deviations for outlier detection
    'CORRELATION_THRESHOLD': 0.3,            # minimum correlation for relationships
    'FREQUENCY_THRESHOLD': 0.1               # minimum frequency for pattern recognition
}

@dataclass
class Insight:
    """Structured insight with confidence scoring"""
    type: str
    message: str
    confidence: float
    data: Dict[str, Any]
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class InsightEngine:
    """Advanced analytics engine for generating insights from memory patterns"""
    
    def __init__(self, memory_processor):
        self.memory_processor = memory_processor
        self.config = INSIGHTS_CONFIG
        logger.info("Insight engine initialized with configuration")
    
    def generate_insights(self, memories: List[Dict[str, Any]]) -> List[Insight]:
        """Generate comprehensive insights from memory data"""
        if not memories or len(memories) < self.config['MIN_SAMPLE_SIZE']:
            logger.warning("Insufficient memory data for insight generation")
            return []
        
        insights = []
        
        try:
            # Generate different types of insights with error handling
            insights.extend(self._analyze_activity_patterns(memories))
            insights.extend(self._analyze_emotion_trends(memories))
            insights.extend(self._analyze_importance_distribution(memories))
            insights.extend(self._analyze_topic_clustering(memories))
            insights.extend(self._analyze_temporal_patterns(memories))
            insights.extend(self._analyze_content_patterns(memories))
            
            # Filter by confidence threshold and limit results
            high_confidence_insights = [
                insight for insight in insights 
                if insight.confidence >= self.config['INSIGHT_CONFIDENCE_THRESHOLD']
            ]
            
            # Group by type and limit each category
            insights_by_type = defaultdict(list)
            for insight in high_confidence_insights:
                insights_by_type[insight.type].append(insight)
            
            final_insights = []
            for insight_type, type_insights in insights_by_type.items():
                # Sort by confidence and take top N
                sorted_insights = sorted(type_insights, key=lambda x: x.confidence, reverse=True)
                final_insights.extend(sorted_insights[:self.config['MAX_INSIGHTS_PER_CATEGORY']])
            
            logger.info("Generated %d insights from %d memories", len(final_insights), len(memories))
            return final_insights
            
        except Exception as e:
            logger.error("Error generating insights: %s", e)
            return []
    
    def _analyze_activity_patterns(self, memories: List[Dict[str, Any]]) -> List[Insight]:
        """Analyze memory creation patterns and activity levels"""
        insights = []
        
        try:
            # Calculate daily activity
            daily_counts = defaultdict(int)
            for memory in memories:
                try:
                    if isinstance(memory.get('timestamp'), (int, float)):
                        date = datetime.fromtimestamp(memory['timestamp']).date()
                    elif isinstance(memory.get('timestamp'), str):
                        date = datetime.fromisoformat(memory['timestamp']).date()
                    else:
                        continue
                    daily_counts[date] += 1
                except (ValueError, TypeError, KeyError):
                    continue
            
            if not daily_counts:
                return insights
            
            avg_daily_activity = statistics.mean(daily_counts.values())
            
            # High activity detection
            if avg_daily_activity > self.config['HIGH_ACTIVITY_THRESHOLD']:
                insights.append(Insight(
                    type="activity_pattern",
                    message=f"High memory activity detected: averaging {avg_daily_activity:.1f} memories per day",
                    confidence=min(0.9, avg_daily_activity / 20),
                    data={"average_daily": avg_daily_activity, "threshold": self.config['HIGH_ACTIVITY_THRESHOLD']}
                ))
            
            # Low activity warning
            elif avg_daily_activity < self.config['LOW_ACTIVITY_THRESHOLD']:
                insights.append(Insight(
                    type="activity_pattern", 
                    message=f"Low memory activity: only {avg_daily_activity:.1f} memories per day on average",
                    confidence=0.8,
                    data={"average_daily": avg_daily_activity, "threshold": self.config['LOW_ACTIVITY_THRESHOLD']}
                ))
            
            # Activity trend analysis
            recent_days = list(daily_counts.values())[-self.config['TREND_ANALYSIS_DAYS']:]
            if len(recent_days) >= 3:
                trend_slope = self._calculate_trend(recent_days)
                if trend_slope > 0.2:
                    insights.append(Insight(
                        type="activity_trend",
                        message="Memory creation is trending upward",
                        confidence=min(0.9, abs(trend_slope) * 2),
                        data={"trend_slope": trend_slope, "recent_days": len(recent_days)}
                    ))
                elif trend_slope < -0.2:
                    insights.append(Insight(
                        type="activity_trend",
                        message="Memory creation is trending downward",
                        confidence=min(0.9, abs(trend_slope) * 2),
                        data={"trend_slope": trend_slope, "recent_days": len(recent_days)}
                    ))
            
        except Exception as e:
            logger.error("Error in activity pattern analysis: %s", e)
        
        return insights
    
    def _analyze_emotion_trends(self, memories: List[Dict[str, Any]]) -> List[Insight]:
        """Analyze emotional patterns and trends in memories"""
        insights = []
        
        try:
            emotion_counts = Counter()
            recent_emotions = []
            
            cutoff_date = datetime.now() - timedelta(days=self.config['TREND_ANALYSIS_DAYS'])
            
            for memory in memories:
                emotion = memory.get('emotion', 'neutral')
                emotion_counts[emotion] += 1
                
                # Track recent emotions for trend analysis
                try:
                    if isinstance(memory.get('timestamp'), (int, float)):
                        mem_date = datetime.fromtimestamp(memory['timestamp'])
                    elif isinstance(memory.get('timestamp'), str):
                        mem_date = datetime.fromisoformat(memory['timestamp'])
                    else:
                        continue
                        
                    if mem_date >= cutoff_date:
                        recent_emotions.append(emotion)
                except (ValueError, TypeError, KeyError):
                    continue
            
            if not emotion_counts:
                return insights
            
            total_memories = sum(emotion_counts.values())
            
            # Dominant emotion detection
            most_common_emotion, count = emotion_counts.most_common(1)[0]
            emotion_percentage = count / total_memories
            
            if emotion_percentage > self.config['FREQUENCY_THRESHOLD'] * 5:  # 50% threshold
                confidence = min(0.9, emotion_percentage * 1.5)
                insights.append(Insight(
                    type="emotion_pattern",
                    message=f"Dominant emotion pattern detected: {most_common_emotion} ({emotion_percentage:.1%} of memories)",
                    confidence=confidence,
                    data={"emotion": most_common_emotion, "percentage": emotion_percentage}
                ))
            
            # Recent emotion trend
            if recent_emotions:
                recent_emotion_counts = Counter(recent_emotions)
                if len(recent_emotion_counts) > 0:
                    recent_dominant = recent_emotion_counts.most_common(1)[0][0]
                    if recent_dominant != most_common_emotion:
                        insights.append(Insight(
                            type="emotion_trend",
                            message=f"Recent emotional shift detected: trending toward {recent_dominant}",
                            confidence=self.config['EMOTION_PATTERN_MIN_CONFIDENCE'],
                            data={"recent_emotion": recent_dominant, "overall_emotion": most_common_emotion}
                        ))
            
            # Emotional diversity
            emotion_diversity = len(emotion_counts) / max(1, len(memories))
            if emotion_diversity > 0.3:
                insights.append(Insight(
                    type="emotion_pattern",
                    message=f"High emotional diversity detected across {len(emotion_counts)} different emotions",
                    confidence=min(0.9, emotion_diversity * 2),
                    data={"diversity_score": emotion_diversity, "unique_emotions": len(emotion_counts)}
                ))
            
        except Exception as e:
            logger.error("Error in emotion trend analysis: %s", e)
        
        return insights
    
    def _analyze_importance_distribution(self, memories: List[Dict[str, Any]]) -> List[Insight]:
        """Analyze the distribution of memory importance scores"""
        insights = []
        
        try:
            importance_scores = []
            for memory in memories:
                score = memory.get('importance_score') or memory.get('importance', 0)
                if isinstance(score, (int, float)) and 0 <= score <= 1:
                    importance_scores.append(score)
            
            if len(importance_scores) < self.config['MIN_SAMPLE_SIZE']:
                return insights
            
            avg_importance = statistics.mean(importance_scores)
            
            # High importance trend
            high_importance_count = sum(1 for score in importance_scores 
                                      if score >= self.config['HIGH_IMPORTANCE_THRESHOLD'])
            high_importance_ratio = high_importance_count / len(importance_scores)
            
            if high_importance_ratio > 0.3:
                insights.append(Insight(
                    type="importance_pattern",
                    message=f"High proportion of important memories: {high_importance_ratio:.1%} are highly important",
                    confidence=min(0.9, high_importance_ratio * 2),
                    data={"high_importance_ratio": high_importance_ratio, "threshold": self.config['HIGH_IMPORTANCE_THRESHOLD']}
                ))
            
            # Low importance warning
            low_importance_count = sum(1 for score in importance_scores 
                                     if score < self.config['MEDIUM_IMPORTANCE_THRESHOLD'])
            low_importance_ratio = low_importance_count / len(importance_scores)
            
            if low_importance_ratio > 0.7:
                insights.append(Insight(
                    type="importance_pattern",
                    message=f"Many memories have low importance scores: {low_importance_ratio:.1%} below medium threshold",
                    confidence=0.8,
                    data={"low_importance_ratio": low_importance_ratio, "threshold": self.config['MEDIUM_IMPORTANCE_THRESHOLD']}
                ))
            
            # Importance trend analysis
            if len(importance_scores) >= self.config['TREND_ANALYSIS_DAYS']:
                recent_scores = importance_scores[-self.config['TREND_ANALYSIS_DAYS']:]
                trend_slope = self._calculate_trend(recent_scores)
                
                if abs(trend_slope) > 0.05:  # Significant trend
                    direction = "increasing" if trend_slope > 0 else "decreasing"
                    insights.append(Insight(
                        type="importance_trend",
                        message=f"Memory importance is {direction} over time",
                        confidence=min(0.9, abs(trend_slope) * 10),
                        data={"trend_slope": trend_slope, "direction": direction}
                    ))
            
        except Exception as e:
            logger.error("Error in importance distribution analysis: %s", e)
        
        return insights
    
    def _analyze_topic_clustering(self, memories: List[Dict[str, Any]]) -> List[Insight]:
        """Analyze topic patterns and clustering in memories"""
        insights = []
        
        try:
            topic_counts = defaultdict(int)
            tag_counts = defaultdict(int)
            
            for memory in memories:
                # Analyze topics
                topics = memory.get('topics', [])
                if isinstance(topics, list):
                    for topic in topics:
                        if isinstance(topic, str) and topic.strip():
                            topic_counts[topic.strip().lower()] += 1
                
                # Analyze tags
                tags = memory.get('tags', [])
                if isinstance(tags, str):
                    try:
                        import json
                        tags = json.loads(tags)
                    except json.JSONDecodeError:
                        tags = [tags]
                
                if isinstance(tags, list):
                    for tag in tags:
                        if isinstance(tag, str) and tag.strip():
                            tag_counts[tag.strip().lower()] += 1
            
            # Topic clustering insights
            if topic_counts:
                dominant_topics = [topic for topic, count in topic_counts.items() 
                                 if count >= self.config['TOPIC_CLUSTERING_MIN_SIZE']]
                
                if dominant_topics:
                    top_topic, count = max(topic_counts.items(), key=lambda x: x[1])
                    topic_ratio = count / len(memories)
                    
                    if topic_ratio > 0.2:
                        insights.append(Insight(
                            type="topic_pattern",
                            message=f"Strong focus on '{top_topic}' topic: {count} memories ({topic_ratio:.1%})",
                            confidence=min(0.9, topic_ratio * 3),
                            data={"top_topic": top_topic, "count": count, "ratio": topic_ratio}
                        ))
            
            # Tag pattern insights
            if tag_counts:
                top_tags = Counter(tag_counts).most_common(3)
                if top_tags:
                    most_used_tag, tag_count = top_tags[0]
                    tag_ratio = tag_count / len(memories)
                    
                    if tag_ratio > 0.25:
                        insights.append(Insight(
                            type="tag_pattern",
                            message=f"Frequently used tag: '{most_used_tag}' appears in {tag_ratio:.1%} of memories",
                            confidence=min(0.9, tag_ratio * 2),
                            data={"top_tag": most_used_tag, "count": tag_count, "ratio": tag_ratio}
                        ))
            
        except Exception as e:
            logger.error("Error in topic clustering analysis: %s", e)
        
        return insights
    
    def _analyze_temporal_patterns(self, memories: List[Dict[str, Any]]) -> List[Insight]:
        """Analyze temporal patterns in memory creation"""
        insights = []
        
        try:
            hour_counts = defaultdict(int)
            day_counts = defaultdict(int)
            
            for memory in memories:
                try:
                    timestamp = memory.get('timestamp')
                    if isinstance(timestamp, (int, float)):
                        dt = datetime.fromtimestamp(timestamp)
                    elif isinstance(timestamp, str):
                        dt = datetime.fromisoformat(timestamp)
                    else:
                        continue
                    
                    hour_counts[dt.hour] += 1
                    day_counts[dt.strftime('%A')] += 1
                    
                except (ValueError, TypeError, KeyError):
                    continue
            
            # Peak hour analysis
            if hour_counts:
                peak_hour = max(hour_counts.items(), key=lambda x: x[1])
                if peak_hour[1] > len(memories) * 0.15:  # 15% of memories in one hour
                    insights.append(Insight(
                        type="temporal_pattern",
                        message=f"Peak memory creation time: {peak_hour[0]:02d}:00 with {peak_hour[1]} memories",
                        confidence=0.8,
                        data={"peak_hour": peak_hour[0], "count": peak_hour[1]}
                    ))
            
            # Day pattern analysis
            if day_counts:
                peak_day = max(day_counts.items(), key=lambda x: x[1])
                if peak_day[1] > len(memories) * 0.2:  # 20% of memories on one day
                    insights.append(Insight(
                        type="temporal_pattern",
                        message=f"Most active day: {peak_day[0]} with {peak_day[1]} memories",
                        confidence=0.8,
                        data={"peak_day": peak_day[0], "count": peak_day[1]}
                    ))
            
        except Exception as e:
            logger.error("Error in temporal pattern analysis: %s", e)
        
        return insights
    
    def _analyze_content_patterns(self, memories: List[Dict[str, Any]]) -> List[Insight]:
        """Analyze content patterns and characteristics"""
        insights = []
        
        try:
            content_lengths = []
            word_counts = []
            
            for memory in memories:
                content = memory.get('text') or memory.get('content', '')
                if isinstance(content, str):
                    content_lengths.append(len(content))
                    word_counts.append(len(content.split()))
            
            if not content_lengths:
                return insights
            
            avg_length = statistics.mean(content_lengths)
            avg_words = statistics.mean(word_counts)
            
            # Long content detection
            if avg_length > 500:
                insights.append(Insight(
                    type="content_pattern",
                    message=f"Detailed memory entries: average {avg_length:.0f} characters per memory",
                    confidence=min(0.9, avg_length / 1000),
                    data={"avg_length": avg_length, "avg_words": avg_words}
                ))
            
            # Short content warning
            elif avg_length < 50:
                insights.append(Insight(
                    type="content_pattern",
                    message=f"Brief memory entries: average only {avg_length:.0f} characters",
                    confidence=0.8,
                    data={"avg_length": avg_length, "avg_words": avg_words}
                ))
            
            # Content variability
            if len(content_lengths) >= self.config['MIN_SAMPLE_SIZE']:
                length_std = statistics.stdev(content_lengths)
                variability = length_std / avg_length if avg_length > 0 else 0
                
                if variability > 1.0:  # High variability
                    insights.append(Insight(
                        type="content_pattern",
                        message="High variability in memory detail levels",
                        confidence=min(0.9, variability / 2),
                        data={"variability": variability, "std_dev": length_std}
                    ))
            
        except Exception as e:
            logger.error("Error in content pattern analysis: %s", e)
        
        return insights
    
    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate trend slope using linear regression"""
        if len(values) < 2:
            return 0.0
        
        try:
            n = len(values)
            x_vals = list(range(n))
            
            # Calculate slope using least squares method
            sum_x = sum(x_vals)
            sum_y = sum(values)
            sum_xy = sum(x * y for x, y in zip(x_vals, values))
            sum_x2 = sum(x * x for x in x_vals)
            
            denominator = n * sum_x2 - sum_x * sum_x
            if denominator == 0:
                return 0.0
            
            slope = (n * sum_xy - sum_x * sum_y) / denominator
            return slope
            
        except (ZeroDivisionError, ValueError):
            return 0.0
    
    def get_memory_stats(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get comprehensive memory statistics"""
        if not memories:
            return {}
        
        try:
            stats = {
                'total_memories': len(memories),
                'emotions': Counter(memory.get('emotion', 'neutral') for memory in memories),
                'avg_importance': 0.0,
                'memory_age_days': 0.0,
                'content_stats': {}
            }
            
            # Calculate importance statistics
            importance_scores = [
                memory.get('importance_score') or memory.get('importance', 0)
                for memory in memories
                if isinstance(memory.get('importance_score') or memory.get('importance', 0), (int, float))
            ]
            
            if importance_scores:
                stats['avg_importance'] = statistics.mean(importance_scores)
                stats['importance_distribution'] = {
                    'high': sum(1 for s in importance_scores if s >= self.config['HIGH_IMPORTANCE_THRESHOLD']),
                    'medium': sum(1 for s in importance_scores if self.config['MEDIUM_IMPORTANCE_THRESHOLD'] <= s < self.config['HIGH_IMPORTANCE_THRESHOLD']),
                    'low': sum(1 for s in importance_scores if s < self.config['MEDIUM_IMPORTANCE_THRESHOLD'])
                }
            
            # Calculate content statistics
            content_lengths = []
            for memory in memories:
                content = memory.get('text') or memory.get('content', '')
                if isinstance(content, str):
                    content_lengths.append(len(content))
            
            if content_lengths:
                stats['content_stats'] = {
                    'avg_length': statistics.mean(content_lengths),
                    'total_characters': sum(content_lengths),
                    'shortest': min(content_lengths),
                    'longest': max(content_lengths)
                }
            
            # Calculate age statistics
            ages = []
            now = datetime.now()
            for memory in memories:
                try:
                    timestamp = memory.get('timestamp')
                    if isinstance(timestamp, (int, float)):
                        mem_date = datetime.fromtimestamp(timestamp)
                    elif isinstance(timestamp, str):
                        mem_date = datetime.fromisoformat(timestamp)
                    else:
                        continue
                    
                    age_days = (now - mem_date).days
                    ages.append(age_days)
                except (ValueError, TypeError, KeyError):
                    continue
            
            if ages:
                stats['memory_age_days'] = statistics.mean(ages)
                stats['age_distribution'] = {
                    'fresh': sum(1 for age in ages if age <= self.config['MEMORY_FRESHNESS_DAYS']),
                    'old': sum(1 for age in ages if age > self.config['MEMORY_FRESHNESS_DAYS'])
                }
            
            return stats
            
        except Exception as e:
            logger.error("Error calculating memory statistics: %s", e)
            return {'error': str(e)}

def create_insight_engine(memory_processor) -> InsightEngine:
    """Factory function to create insight engine with proper configuration"""
    return InsightEngine(memory_processor)
