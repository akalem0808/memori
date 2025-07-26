from fastapi.testclient import TestClient
import pytest
import json
import os
from datetime import datetime
from memory_api import app
from memory_model import Memory
from memory_utils import MemoryProcessor

client = TestClient(app)

# Fixtures
@pytest.fixture
def test_memory():
    """Create a test memory object"""
    return Memory(
        id="test-memory-1",
        text="This is a test memory",
        timestamp=datetime.now(),
        emotion="happy",
        emotion_scores={"happy": 0.8, "neutral": 0.2},
        tags=["test", "memory"],
        topics=["testing"],
        importance_score=0.7
    )

@pytest.fixture
def memory_processor():
    """Create a test memory processor with temporary database"""
    test_db_path = "test_memory_system.db"
    processor = MemoryProcessor(db_path=test_db_path)
    yield processor
    
    # Cleanup
    try:
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
    except:
        pass

# API Tests
def test_root():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "version" in response.json()

def test_demo_memories():
    """Test demo memories endpoint"""
    response = client.get("/memories/demo")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0

def test_get_memories():
    """Test retrieving memories list"""
    response = client.get("/memories")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_create_text_memory():
    """Test creating a memory from text"""
    memory_data = {
        "text": "This is a new test memory",
        "metadata": {"source": "test"}
    }
    response = client.post("/memories/text", json=memory_data)
    assert response.status_code == 201
    assert "id" in response.json()
    assert response.json()["text"] == memory_data["text"]

def test_get_memory_by_id():
    """Test retrieving a specific memory by ID"""
    # First create a memory
    memory_data = {
        "text": "Memory to retrieve by ID",
        "metadata": {"source": "test"}
    }
    create_response = client.post("/memories/text", json=memory_data)
    memory_id = create_response.json()["id"]
    
    # Then retrieve it
    response = client.get(f"/memories/{memory_id}")
    assert response.status_code == 200
    assert response.json()["id"] == memory_id
    assert response.json()["text"] == memory_data["text"]

def test_search_memories():
    """Test searching memories"""
    # Create some test memories first
    client.post("/memories/text", json={"text": "Keyword apple in this memory"})
    client.post("/memories/text", json={"text": "Another memory about oranges"})
    
    # Search for the keyword
    response = client.get("/memories/search?q=apple")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    
    # At least one result should contain our keyword
    found = False
    for memory in response.json():
        if "apple" in memory["text"].lower():
            found = True
            break
    
    assert found, "Search did not return memory with keyword"

def test_filter_memories():
    """Test filtering memories"""
    # Create test memories with different emotions
    client.post("/memories/text", json={"text": "Happy memory", "emotion": "happy"})
    client.post("/memories/text", json={"text": "Sad memory", "emotion": "sad"})
    
    # Filter by emotion
    response = client.get("/memories?emotion=happy")
    assert response.status_code == 200
    
    # All results should have the filtered emotion
    for memory in response.json():
        assert memory["emotion"] == "happy"

def test_memory_stats():
    """Test memory statistics endpoint"""
    response = client.get("/memories/stats")
    assert response.status_code == 200
    assert "totalMemories" in response.json()

# Memory Processor Tests
def test_memory_processor_store(memory_processor, test_memory):
    """Test storing a memory with MemoryProcessor"""
    memory_processor.store_memory(test_memory)
    
    # Verify it was stored
    memories = memory_processor.get_memories()
    assert len(memories) > 0
    assert any(m.id == test_memory.id for m in memories)

def test_memory_processor_retrieve(memory_processor, test_memory):
    """Test retrieving a memory with MemoryProcessor"""
    memory_processor.store_memory(test_memory)
    
    # Retrieve by ID
    retrieved = memory_processor.get_memory_by_id(test_memory.id)
    assert retrieved is not None
    assert retrieved.id == test_memory.id
    assert retrieved.text == test_memory.text

def test_memory_processor_search(memory_processor):
    """Test searching memories with MemoryProcessor"""
    # Create test memories
    memory1 = Memory(
        id="search-test-1",
        text="This memory contains apples",
        timestamp=datetime.now(),
        emotion="neutral"
    )
    
    memory2 = Memory(
        id="search-test-2",
        text="This memory contains bananas",
        timestamp=datetime.now(),
        emotion="neutral"
    )
    
    memory_processor.store_memory(memory1)
    memory_processor.store_memory(memory2)
    
    # Search for apples
    results = memory_processor.search_memories("apples")
    assert len(results) > 0
    assert any(m.id == "search-test-1" for m in results)
    assert not any(m.id == "search-test-2" for m in results)

def test_memory_processor_filter(memory_processor):
    """Test filtering memories with MemoryProcessor"""
    # Create test memories with different emotions
    memory1 = Memory(
        id="filter-test-1",
        text="Happy memory",
        timestamp=datetime.now(),
        emotion="happy"
    )
    
    memory2 = Memory(
        id="filter-test-2",
        text="Sad memory",
        timestamp=datetime.now(),
        emotion="sad"
    )
    
    memory_processor.store_memory(memory1)
    memory_processor.store_memory(memory2)
    
    # Filter by emotion
    results = memory_processor.filter_memories({"emotion": "happy"})
    assert len(results) > 0
    assert all(m.emotion == "happy" for m in results)
    assert not any(m.id == "filter-test-2" for m in results)
