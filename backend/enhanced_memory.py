# DEPRECATED: Use Memory model instead
"""
This module has been deprecated. Use Memory model from memory_model.py instead.
"""

class EnhancedMemory:
    """Obsolete: Use Memory model instead"""
    def __init__(self, memory_id, timestamp, audio_text, emotion, embedding, movement_data, context_data, importance_score, tags):
        self.memory_id = memory_id
        self.timestamp = timestamp
        self.audio_text = audio_text
        self.emotion = emotion
        self.enhanced_embedding = embedding
        self.movement_data = movement_data
        self.context_data = context_data
        self.importance_score = importance_score
        self.searchable_tags = tags

    def to_dict(self):
        return {
            'id': self.memory_id,
            'timestamp': self.timestamp,
            'audio_text': self.audio_text,
            'emotion': self.emotion,
            'enhanced_embedding': self.enhanced_embedding,
            'movement_data': self.movement_data,
            'context_data': self.context_data,
            'importance_score': self.importance_score,
            'searchable_tags': self.searchable_tags
        }
