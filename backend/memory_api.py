# FastAPI HTTP API Layer - Complete Implementation
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import json
import uuid
import tempfile
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Import your custom modules
from memory_utils import MemoryProcessor
from audio_memory_assistant import AudioMemoryAssistant
from enhanced_memory import EnhancedMemory
from memory_model import Memory
from auth import Token, User, authenticate_user, create_access_token, get_current_active_user
from auth import READ_PERMISSION, WRITE_PERMISSION, ADMIN_PERMISSION

# Load environment variables
load_dotenv()
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# FastAPI app with metadata
app = FastAPI(
    title="Memori API",
    description="Audio Memory Processing System",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enhanced Pydantic models
class MemoryRequest(BaseModel):
    text: str
    metadata: Optional[Dict[str, Any]] = None

class MemoryResponse(BaseModel):
    id: str
    text: str
    emotion: str
    emotion_scores: Dict[str, float]
    tags: List[str]
    topics: List[str]
    importance_score: float
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None

class SearchRequest(BaseModel):
    query: Optional[str] = None
    emotion: Optional[str] = None
    tags: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

class AnalyticsResponse(BaseModel):
    total_memories: int
    emotion_distribution: Dict[str, int]
    top_topics: List[str]
    average_importance: float

class HealthResponse(BaseModel):
    status: str
    version: str
    dependencies: Dict[str, str]

# Global instances (in production, use proper dependency injection)
memory_processor = None
audio_assistant = None

def get_memory_processor():
    """Dependency injection for MemoryProcessor"""
    global memory_processor
    if memory_processor is None:
        memory_processor = MemoryProcessor()
    return memory_processor

def get_audio_assistant():
    """Dependency injection for AudioMemoryAssistant"""
    global audio_assistant, memory_processor
    if audio_assistant is None:
        if memory_processor is None:
            memory_processor = MemoryProcessor()
        audio_assistant = AudioMemoryAssistant(memory_processor=memory_processor)
    return audio_assistant

# Health check endpoint
@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        dependencies={
            "database": "connected",
            "ai_models": "loaded"
        }
    )

# Memory CRUD operations
@app.post("/memories", response_model=MemoryResponse)
def create_memory(req: MemoryRequest, processor=Depends(get_memory_processor)):
    """Create a new memory from text"""
    try:
        # Process the text memory
        memory_data = processor.process_text_memory(req.text, req.metadata)
        return MemoryResponse(**memory_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create memory: {str(e)}")

@app.post("/memories/audio", response_model=MemoryResponse)
async def upload_audio_memory(
    file: UploadFile = File(...),
    metadata: Optional[str] = None,
    audio_assistant=Depends(get_audio_assistant)
):
    """Upload and process an audio file to create a memory"""
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('audio/'):
            raise HTTPException(status_code=400, detail="File must be an audio file")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # Process audio file
            metadata_dict = json.loads(metadata) if metadata else None
            memory_data = audio_assistant.process_audio_file(temp_file_path, metadata_dict)
            
            if not memory_data:
                raise HTTPException(status_code=400, detail="No speech detected in audio file")
            
            # No need to store in main memory system - AudioMemoryAssistant already does this now
            # Return memory data as dict for API response
            return memory_data.dict()
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process audio: {str(e)}")

@app.get("/memories/{memory_id}", response_model=MemoryResponse)
def get_memory(memory_id: str, processor=Depends(get_memory_processor)):
    """Get a specific memory by ID"""
    try:
        memory = processor.get_memory(memory_id)
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")
        # Handle Memory object by converting to dict
        if isinstance(memory, Memory):
            memory = memory.dict()
        return MemoryResponse(**memory)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve memory: {str(e)}")

@app.get("/memories", response_model=List[MemoryResponse])
def list_memories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    processor=Depends(get_memory_processor)
):
    """List memories with pagination"""
    try:
        memories = processor.list_memories(skip=skip, limit=limit)
        # Handle Memory objects by converting to dicts
        return [MemoryResponse(**(m.dict() if isinstance(m, Memory) else m)) for m in memories]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list memories: {str(e)}")

@app.post("/memories/search", response_model=List[MemoryResponse])
def search_memories(search_req: SearchRequest, processor=Depends(get_memory_processor)):
    """Search memories based on various criteria"""
    try:
        memories = processor.search_memories(
            query=search_req.query,
            emotion=search_req.emotion,
            tags=search_req.tags,
            date_from=search_req.date_from,
            date_to=search_req.date_to
        )
        # Handle Memory objects by converting to dicts
        return [MemoryResponse(**(m.dict() if isinstance(m, Memory) else m)) for m in memories]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.delete("/memories/{memory_id}")
def delete_memory(memory_id: str, processor=Depends(get_memory_processor)):
    """Delete a memory"""
    try:
        success = processor.delete_memory(memory_id)
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {"message": "Memory deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete memory: {str(e)}")

@app.put("/memories/{memory_id}", response_model=MemoryResponse)
def update_memory(
    memory_id: str, 
    req: MemoryRequest, 
    processor=Depends(get_memory_processor)
):
    """Update a memory"""
    try:
        memory = processor.update_memory(memory_id, req.text, req.metadata)
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")
        # Handle Memory object by converting to dict
        if isinstance(memory, Memory):
            memory = memory.dict()
        return MemoryResponse(**memory)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update memory: {str(e)}")

# Analytics endpoints
@app.get("/analytics", response_model=AnalyticsResponse)
def get_analytics(processor=Depends(get_memory_processor)):
    """Get memory analytics and statistics"""
    try:
        analytics = processor.get_analytics()
        return AnalyticsResponse(**analytics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")

@app.get("/analytics/emotions")
def get_emotion_trends(
    days: int = Query(30, ge=1, le=365),
    processor=Depends(get_memory_processor)
):
    """Get emotion trends over time"""
    try:
        trends = processor.get_emotion_trends(days)
        return {"trends": trends}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get emotion trends: {str(e)}")

# Export endpoints
@app.get("/export/json")
def export_memories_json(processor=Depends(get_memory_processor)):
    """Export all memories as JSON"""
    try:
        export_data = processor.export_memories("json")
        return {"data": export_data, "format": "json"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@app.get("/export/csv")
def export_memories_csv(processor=Depends(get_memory_processor)):
    """Export all memories as CSV"""
    try:
        csv_data = processor.export_memories("csv")
        return {"data": csv_data, "format": "csv"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

# Bulk operations
@app.post("/memories/bulk-delete")
def bulk_delete_memories(
    memory_ids: List[str], 
    processor=Depends(get_memory_processor)
):
    """Delete multiple memories"""
    try:
        deleted_count = processor.bulk_delete_memories(memory_ids)
        return {"message": f"Deleted {deleted_count} memories"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk delete failed: {str(e)}")

# Vector similarity search
@app.post("/memories/similar")
def find_similar_memories(
    request: MemoryRequest,
    limit: int = Query(10, ge=1, le=50),
    processor=Depends(get_memory_processor)
):
    """Find memories similar to given text"""
    try:
        similar_memories = processor.find_similar_memories(request.text, limit)
        # Handle Memory objects by converting to dicts
        return [MemoryResponse(**(m.dict() if isinstance(m, Memory) else m)) for m in similar_memories]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Similarity search failed: {str(e)}")

# Enhanced error handling
@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    """Global exception handler"""
    return HTTPException(status_code=500, detail=f"Internal server error: {str(exc)}")

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global memory_processor, audio_assistant
    try:
        print("🚀 Initializing Memori API...")
        memory_processor = MemoryProcessor()
        audio_assistant = AudioMemoryAssistant(memory_processor=memory_processor)
        print("✅ Memori API started successfully")
    except Exception as e:
        print(f"❌ Failed to start Memori API: {e}")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    global memory_processor, audio_assistant
    try:
        if memory_processor:
            memory_processor.close()
        if audio_assistant:
            audio_assistant.close()
        print("✅ Memori API shut down gracefully")
    except Exception as e:
        print(f"⚠️ Error during shutdown: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
