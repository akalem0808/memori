import pytest
import time
import threading
from queue import Queue
from memory_model import Memory
from memory_utils import MemoryProcessor
from advanced_features import RealTimeMemoryProcessor

# Test the real-time memory processing
def test_realtime_memory_processor():
    """Test the real-time memory processor"""
    # Create test processor and memory
    processor = MemoryProcessor(db_path="test_realtime.db")
    realtime_processor = RealTimeMemoryProcessor(processor)
    
    # Create a callback to capture events
    events = []
    
    def test_callback(event_data):
        events.append(event_data)
    
    # Subscribe to events
    realtime_processor.subscribe(test_callback)
    
    # Start processing
    realtime_processor.start_processing()
    
    try:
        # Queue a memory
        test_memory = Memory(
            id="realtime-test-1",
            text="This is a real-time test memory",
            timestamp=time.time(),
            emotion="happy"
        )
        
        realtime_processor.queue_memory(test_memory.to_dict())
        
        # Wait for processing
        time.sleep(2)
        
        # Verify event was received
        assert len(events) > 0
        assert events[0]['event_type'] == 'new_memory'
        assert events[0]['memory_id'] == 'realtime-test-1'
    
    finally:
        # Stop processing
        realtime_processor.stop_processing()

# Test memory insights generation
def test_memory_insights():
    """Test generating insights from memories"""
    # Create test processor
    processor = MemoryProcessor(db_path="test_insights.db")
    realtime_processor = RealTimeMemoryProcessor(processor)
    
    # Create test memories with same emotion to trigger pattern insight
    memories = [
        Memory(
            id=f"insight-test-{i}",
            text=f"Test memory {i}",
            timestamp=time.time() - (3-i)*3600,  # Different times
            emotion="surprised"  # Same emotion to trigger pattern
        )
        for i in range(1, 4)
    ]
    
    # Generate insights
    insights = realtime_processor._generate_insights(memories)
    
    # Verify insights were generated
    assert len(insights) > 0
    assert insights[0]['insight_type'] == 'pattern'
    assert 'surprised' in insights[0]['title']

# Test audio buffer processing
def test_audio_buffer_processing(monkeypatch):
    """Test processing of audio buffer chunks"""
    # Create test processor
    processor = MemoryProcessor(db_path="test_audio.db")
    realtime_processor = RealTimeMemoryProcessor(processor)
    
    # Mock the whisper transcription to avoid actual audio processing
    class MockWhisperModel:
        def transcribe(self, audio_path):
            return {"text": "This is a test transcription"}
    
    # Mock the emotion analyzer
    def mock_emotion_analyzer(text):
        return [{"label": "happy", "score": 0.9}]
    
    # Apply mocks
    monkeypatch.setattr(processor, "get_whisper_model", lambda: MockWhisperModel())
    monkeypatch.setattr(processor, "get_emotion_analyzer", lambda: mock_emotion_analyzer)
    
    # Create a callback to capture events
    events = []
    
    def test_callback(event_data):
        events.append(event_data)
    
    # Subscribe to events
    realtime_processor.subscribe(test_callback)
    
    # Create mock audio chunks
    audio_chunks = [
        {
            'data': b'test_audio_data',
            'metadata': {'source': 'test'}
        }
        for _ in range(3)
    ]
    
    # Process audio buffer
    realtime_processor._process_audio_buffer(audio_chunks)
    
    # Verify event was received
    assert len(events) > 0
    assert events[0]['event_type'] == 'streaming_transcription'
    assert events[0]['text'] == "This is a test transcription"
    assert events[0]['emotion'] == "happy"
