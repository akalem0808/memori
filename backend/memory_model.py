# Unified Memory Data Model
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime

class Memory(BaseModel):
    """Unified memory data model for all components"""
    id: str
    text: str
    timestamp: datetime
    emotion: str = "neutral"
    emotion_scores: Dict[str, float] = {}
    tags: List[str] = []
    topics: List[str] = []
    importance_score: float = 0.5
    embedding: Optional[List[float]] = None
    source_type: Literal['text', 'audio'] = 'text'
    metadata: Dict[str, Any] = {}
    
    # Audio-specific fields
    audio_text: Optional[str] = None
    enhanced_embedding: Optional[List[float]] = None
    
    # Multimodal fields
    movement_data: Optional[Dict[str, Any]] = None
    context_data: Optional[Dict[str, Any]] = None
    searchable_tags: List[str] = []
    
    class Config:
        # Allow datetime objects
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        data = self.dict()
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Memory':
        """Create Memory from dictionary"""
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)
