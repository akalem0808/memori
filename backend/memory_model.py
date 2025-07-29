# Enhanced Memory Model with Validation and Security
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field, validator, root_validator
import json
import logging

logger = logging.getLogger(__name__)

class Memory(BaseModel):
    """Enhanced Memory model with comprehensive validation and security"""
    
    id: str = Field(..., min_length=1, max_length=100, description="Unique memory identifier")
    content: str = Field(..., min_length=1, max_length=10000, description="Memory content text", alias="text")
    emotion: str = Field(default="neutral", max_length=50, description="Detected emotion")
    importance: float = Field(default=0.0, ge=0.0, le=1.0, description="Importance score", alias="importance_score")
    created_at: Union[str, datetime] = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    updated_at: Optional[Union[str, datetime]] = Field(default=None, description="Last update timestamp")
    tags: List[str] = Field(default_factory=list, max_items=20, description="Memory tags")
    context: str = Field(default="", max_length=2000, description="Additional context")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    # Legacy fields for backward compatibility
    emotion_scores: Dict[str, float] = Field(default_factory=dict, description="Emotion confidence scores")
    topics: List[str] = Field(default_factory=list, max_items=10, description="Related topics")
    timestamp: Optional[Union[str, datetime, float]] = Field(default=None, description="Legacy timestamp field")
    embedding: Optional[List[float]] = Field(default=None, description="Vector embedding")
    
    class Config:
        allow_population_by_field_name = True
        extra = "forbid"  # Prevent additional fields for security
        validate_assignment = True
        
    @validator('content', 'context', pre=True)
    def validate_text_fields(cls, v):
        """Validate and sanitize text fields"""
        if not v:
            return ""
        if isinstance(v, str):
            # Basic sanitization - remove null bytes and control characters
            v = v.replace('\x00', '').strip()
            # Limit length to prevent memory issues
            if len(v) > 50000:
                logger.warning("Text field truncated due to excessive length")
                v = v[:50000]
            return v
        return str(v)
    
    @validator('emotion', pre=True)
    def validate_emotion(cls, v):
        """Validate emotion field"""
        if not v:
            return "neutral"
        # Sanitize and validate emotion values
        valid_emotions = {
            'joy', 'sadness', 'anger', 'fear', 'surprise', 'disgust', 
            'neutral', 'positive', 'negative', 'happy', 'sad'
        }
        emotion = str(v).lower().strip()
        if emotion in valid_emotions:
            return emotion
        return "neutral"
    
    @validator('tags', pre=True)
    def validate_tags(cls, v):
        """Validate and sanitize tags"""
        if not v:
            return []
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = [v]  # Single tag as string
        
        if isinstance(v, list):
            sanitized_tags = []
            for tag in v[:20]:  # Limit to 20 tags
                if isinstance(tag, str) and tag.strip():
                    clean_tag = tag.strip().lower()[:50]  # Limit tag length
                    if clean_tag and clean_tag not in sanitized_tags:
                        sanitized_tags.append(clean_tag)
            return sanitized_tags
        return []
    
    @validator('topics', pre=True)
    def validate_topics(cls, v):
        """Validate and sanitize topics"""
        if not v:
            return []
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = [v]
        
        if isinstance(v, list):
            sanitized_topics = []
            for topic in v[:10]:  # Limit to 10 topics
                if isinstance(topic, str) and topic.strip():
                    clean_topic = topic.strip().lower()[:100]
                    if clean_topic and clean_topic not in sanitized_topics:
                        sanitized_topics.append(clean_topic)
            return sanitized_topics
        return []
    
    @validator('emotion_scores', pre=True)
    def validate_emotion_scores(cls, v):
        """Validate emotion scores dictionary"""
        if not v:
            return {}
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                return {}
        
        if isinstance(v, dict):
            validated_scores = {}
            for emotion, score in v.items():
                if isinstance(emotion, str) and emotion.strip():
                    try:
                        score_float = float(score)
                        if 0.0 <= score_float <= 1.0:
                            validated_scores[emotion.strip().lower()] = score_float
                    except (ValueError, TypeError):
                        continue
            return validated_scores
        return {}
    
    @validator('metadata', pre=True)
    def validate_metadata(cls, v):
        """Validate metadata dictionary"""
        if not v:
            return {}
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                return {}
        
        if isinstance(v, dict):
            # Limit metadata size and sanitize
            sanitized_metadata = {}
            for key, value in v.items():
                if isinstance(key, str) and len(key) <= 100:
                    # Convert value to JSON-serializable format
                    try:
                        json.dumps(value)  # Test if serializable
                        sanitized_metadata[key] = value
                        if len(sanitized_metadata) >= 50:  # Limit metadata entries
                            break
                    except (TypeError, ValueError):
                        continue
            return sanitized_metadata
        return {}
    
    @validator('created_at', 'updated_at', 'timestamp', pre=True)
    def validate_datetime_fields(cls, v, field):
        """Validate and normalize datetime fields"""
        if v is None:
            if field.name == 'created_at':
                return datetime.now(timezone.utc)
            return None
        
        # Handle different timestamp formats
        if isinstance(v, datetime):
            # Ensure timezone awareness
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            return v
        
        if isinstance(v, (int, float)):
            try:
                return datetime.fromtimestamp(v, tz=timezone.utc)
            except (ValueError, OSError):
                return datetime.now(timezone.utc)
        
        if isinstance(v, str):
            # Try to parse ISO format
            try:
                dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                try:
                    # Try parsing as timestamp
                    timestamp = float(v)
                    return datetime.fromtimestamp(timestamp, tz=timezone.utc)
                except ValueError:
                    return datetime.now(timezone.utc)
        
        return datetime.now(timezone.utc)
    
    @root_validator
    def validate_consistency(cls, values):
        """Validate data consistency across fields"""
        # Ensure updated_at is not before created_at
        created_at = values.get('created_at')
        updated_at = values.get('updated_at')
        
        if created_at and updated_at:
            if isinstance(created_at, datetime) and isinstance(updated_at, datetime):
                if updated_at < created_at:
                    values['updated_at'] = created_at
        
        # Set updated_at to created_at if not provided
        if not updated_at and created_at:
            values['updated_at'] = created_at
        
        # Validate importance vs emotion_scores consistency
        emotion_scores = values.get('emotion_scores', {})
        if emotion_scores and 'importance' not in values:
            # Calculate importance from emotion scores if not provided
            max_score = max(emotion_scores.values()) if emotion_scores else 0.5
            values['importance'] = min(max_score, 1.0)
        
        return values
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with consistent datetime formatting"""
        data = self.dict(by_alias=True)
        
        # Ensure consistent datetime formatting
        for field in ['created_at', 'updated_at', 'timestamp']:
            if field in data and data[field]:
                if isinstance(data[field], datetime):
                    data[field] = data[field].isoformat()
                elif isinstance(data[field], (int, float)):
                    data[field] = datetime.fromtimestamp(data[field], tz=timezone.utc).isoformat()
        
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string with proper serialization"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=None)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Memory':
        """Create Memory instance from dictionary with validation"""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Memory':
        """Create Memory instance from JSON string"""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}") from e
    
    def update_timestamp(self):
        """Update the updated_at timestamp"""
        self.updated_at = datetime.now(timezone.utc)
    
    def add_tag(self, tag: str):
        """Add a tag if not already present"""
        if isinstance(tag, str) and tag.strip():
            clean_tag = tag.strip().lower()
            if clean_tag not in self.tags and len(self.tags) < 20:
                self.tags.append(clean_tag)
    
    def remove_tag(self, tag: str):
        """Remove a tag if present"""
        if isinstance(tag, str):
            clean_tag = tag.strip().lower()
            if clean_tag in self.tags:
                self.tags.remove(clean_tag)
    
    def get_age_in_days(self) -> float:
        """Get the age of the memory in days"""
        if isinstance(self.created_at, datetime):
            now = datetime.now(timezone.utc)
            if self.created_at.tzinfo is None:
                created_at = self.created_at.replace(tzinfo=timezone.utc)
            else:
                created_at = self.created_at
            delta = now - created_at
            return delta.total_seconds() / 86400  # seconds in a day
        return 0.0
    
    def is_important(self, threshold: float = 0.7) -> bool:
        """Check if memory is considered important"""
        return self.importance >= threshold
    
    def __str__(self) -> str:
        """String representation"""
        return f"Memory(id={self.id[:8]}..., emotion={self.emotion}, importance={self.importance:.2f})"
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return (f"Memory(id='{self.id}', content='{self.content[:50]}...', "
                f"emotion='{self.emotion}', importance={self.importance})")

# Legacy alias for backward compatibility
EnhancedMemory = Memory
