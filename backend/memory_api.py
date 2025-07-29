# FastAPI HTTP API Layer - Complete Implementation
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Query, status, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import RedirectResponse, FileResponse
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
import os
import json
import tempfile
import logging
import hashlib
import magic
from datetime import datetime, timedelta
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Import your custom modules
from memory_utils import MemoryProcessor
from audio_memory_assistant import AudioMemoryAssistant
from memory_model import Memory

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security and configuration constants
SECURITY_CONFIG = {
    'MAX_FILE_SIZE': int(os.getenv('MAX_FILE_SIZE', '50_000_000')),  # 50MB default
    'ALLOWED_AUDIO_TYPES': {
        'audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/mp4', 
        'audio/m4a', 'audio/ogg', 'audio/flac', 'audio/webm'
    },
    'ALLOWED_ORIGINS': os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:8080').split(','),
    'UPLOAD_CHUNK_SIZE': 8192,  # 8KB chunks for streaming
    'TEMP_FILE_PREFIX': 'memori_upload_',
    'MAX_METADATA_SIZE': 10000,  # 10KB max metadata
    'RATE_LIMIT_REQUESTS': int(os.getenv('RATE_LIMIT_REQUESTS', '100')),
    'RATE_LIMIT_WINDOW': int(os.getenv('RATE_LIMIT_WINDOW', '60'))
}

# Application state manager
class AppState:
    """Centralized application state management"""
    def __init__(self):
        self.memory_processor: Optional[MemoryProcessor] = None
        self.audio_assistant: Optional[AudioMemoryAssistant] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize application components"""
        if self._initialized:
            return
            
        try:
            logger.info("Initializing application components...")
            self.memory_processor = MemoryProcessor()
            self.audio_assistant = AudioMemoryAssistant(memory_processor=self.memory_processor)
            self._initialized = True
            logger.info("Application components initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize application components: %s", e)
            raise
    
    async def cleanup(self):
        """Clean up application resources"""
        try:
            if self.memory_processor:
                self.memory_processor.close()
            if self.audio_assistant:
                self.audio_assistant.close()
            logger.info("Application components cleaned up successfully")
        except Exception as e:
            logger.error("Error during cleanup: %s", e)
    
    def get_memory_processor(self) -> MemoryProcessor:
        if not self._initialized or not self.memory_processor:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Memory processor not initialized"
            )
        return self.memory_processor
    
    def get_audio_assistant(self) -> AudioMemoryAssistant:
        if not self._initialized or not self.audio_assistant:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Audio assistant not initialized"
            )
        return self.audio_assistant

# Global application state
app_state = AppState()

# Lifespan context manager for proper startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    # Startup
    await app_state.initialize()
    yield
    # Shutdown
    await app_state.cleanup()

# FastAPI app with enhanced configuration
app = FastAPI(
    title="Memori API",
    description="Secure Audio Memory Processing System",
    version="1.0.0",
    lifespan=lifespan
)

# Security middleware configuration
if os.getenv('ENVIRONMENT') == 'production':
    # Production CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=SECURITY_CONFIG['ALLOWED_ORIGINS'],
        allow_credentials=False,  # Don't allow credentials with wildcard origins
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
        max_age=3600,
    )
    
    # Add trusted host middleware for production
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=os.getenv('ALLOWED_HOSTS', 'localhost').split(',')
    )
else:
    # Development CORS configuration  
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:8080", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# File validation utilities
def validate_file_type(file: UploadFile) -> bool:
    """Validate file type using both content-type and magic numbers"""
    # Check content type
    if not file.content_type or file.content_type not in SECURITY_CONFIG['ALLOWED_AUDIO_TYPES']:
        return False
    
    # Additional validation could be added here with python-magic
    # For now, we rely on content-type and file extension
    if file.filename:
        allowed_extensions = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.webm', '.mp4'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        return file_ext in allowed_extensions
    
    return True

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks"""
    if not filename:
        return "unknown_file"
    
    # Remove path components
    filename = os.path.basename(filename)
    
    # Remove dangerous characters
    allowed_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    sanitized = ''.join(c for c in filename if c in allowed_chars)
    
    # Ensure it's not empty and not too long
    if not sanitized:
        sanitized = "unknown_file"
    
    return sanitized[:255]  # Limit length

# Enhanced Pydantic models with validation
class MemoryRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000, description="Memory text content")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")
    
    @validator('text')
    def validate_text(cls, v):
        if not v or not v.strip():
            raise ValueError('Text content cannot be empty')
        return v.strip()
    
    @validator('metadata')
    def validate_metadata(cls, v):
        if v is not None:
            # Limit metadata size when serialized
            metadata_json = json.dumps(v)
            if len(metadata_json) > SECURITY_CONFIG['MAX_METADATA_SIZE']:
                raise ValueError(f'Metadata too large (max {SECURITY_CONFIG["MAX_METADATA_SIZE"]} bytes)')
        return v

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
    query: Optional[str] = Field(None, max_length=1000)
    emotion: Optional[str] = Field(None, max_length=50)
    tags: Optional[List[str]] = Field(None, max_items=20)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    
    @validator('tags')
    def validate_tags(cls, v):
        if v:
            # Validate each tag
            for tag in v:
                if not isinstance(tag, str) or len(tag) > 100:
                    raise ValueError('Each tag must be a string with max 100 characters')
        return v

class AnalyticsResponse(BaseModel):
    total_memories: int
    emotion_distribution: Dict[str, int]
    top_topics: List[str]
    average_importance: float

class HealthResponse(BaseModel):
    status: str
    version: str
    dependencies: Dict[str, str]
    uptime: Optional[float] = None

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime

# Dependency injection functions
def get_memory_processor() -> MemoryProcessor:
    """Dependency injection for MemoryProcessor"""
    return app_state.get_memory_processor()

def get_audio_assistant() -> AudioMemoryAssistant:
    """Dependency injection for AudioMemoryAssistant"""
    return app_state.get_audio_assistant()

# Enhanced error handling
class APIError(Exception):
    """Custom API error with structured information"""
    def __init__(self, message: str, status_code: int = 500, error_code: str = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)

@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    """Handle custom API errors"""
    logger.error("API Error: %s (code: %s)", exc.message, exc.error_code)
    return ErrorResponse(
        detail=exc.message,
        error_code=exc.error_code,
        timestamp=datetime.utcnow()
    )

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle validation errors"""
    logger.warning("Validation error: %s", str(exc))
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc)
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Global exception handler with logging"""
    logger.error("Unexpected error: %s", str(exc), exc_info=True)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred. Please try again later."
    )

# Root route
@app.get("/")
async def root():
    """Root endpoint - redirect to API documentation"""
    return RedirectResponse(url="/docs")

# Favicon route
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve favicon or return empty response"""
    try:
        favicon_path = os.path.join(os.path.dirname(__file__), "../static/favicon.ico")
        if os.path.exists(favicon_path):
            return FileResponse(favicon_path, media_type="image/x-icon")
    except Exception as e:
        logger.warning("Could not serve favicon: %s", e)
    
    return Response(content=b"", media_type="image/x-icon")

# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Enhanced health check endpoint"""
    try:
        # Check if services are available
        memory_processor = app_state.get_memory_processor()
        audio_assistant = app_state.get_audio_assistant()
        
        return HealthResponse(
            status="healthy",
            version="1.0.0",
            dependencies={
                "database": "connected" if memory_processor else "disconnected",
                "audio_processor": "loaded" if audio_assistant else "not_loaded",
                "ai_models": "loaded"
            }
        )
    except Exception as e:
        logger.error("Health check failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy"
        )

# Memory CRUD operations with enhanced validation
@app.post("/memories", response_model=MemoryResponse)
async def create_memory(
    request: MemoryRequest, 
    processor: MemoryProcessor = Depends(get_memory_processor)
):
    """Create a new memory from text with validation"""
    try:
        logger.info("Creating text memory with %d characters", len(request.text))
        
        # Process the text memory
        memory_data = processor.process_text_memory(request.text, request.metadata)
        
        # Convert Memory object to response format
        if isinstance(memory_data, Memory):
            memory_dict = memory_data.dict()
            if isinstance(memory_data.timestamp, datetime):
                memory_dict["timestamp"] = memory_data.timestamp.timestamp()
            return MemoryResponse(**memory_dict)
        else:
            return MemoryResponse(**memory_data)
            
    except Exception as e:
        logger.error("Failed to create text memory: %s", e)
        raise APIError(
            message=f"Failed to create memory: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="MEMORY_CREATION_FAILED"
        )

@app.post("/memories/audio", response_model=MemoryResponse)
async def upload_audio_memory(
    file: UploadFile = File(..., description="Audio file to process"),
    metadata: Optional[str] = Query(None, max_length=SECURITY_CONFIG['MAX_METADATA_SIZE']),
    audio_assistant: AudioMemoryAssistant = Depends(get_audio_assistant)
):
    """Upload and process an audio file with enhanced security"""
    temp_file_path = None
    
    try:
        # File size validation
        if hasattr(file, 'size') and file.size and file.size > SECURITY_CONFIG['MAX_FILE_SIZE']:
            raise APIError(
                message=f"File too large. Maximum size: {SECURITY_CONFIG['MAX_FILE_SIZE']} bytes",
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                error_code="FILE_TOO_LARGE"
            )
        
        # File type validation
        if not validate_file_type(file):
            raise APIError(
                message="Invalid file type. Allowed types: " + ", ".join(SECURITY_CONFIG['ALLOWED_AUDIO_TYPES']),
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="INVALID_FILE_TYPE"
            )
        
        # Sanitize filename
        safe_filename = sanitize_filename(file.filename or "unknown_audio")
        logger.info("Processing audio file: %s (type: %s)", safe_filename, file.content_type)
        
        # Create secure temporary file
        temp_dir = tempfile.gettempdir()
        temp_fd, temp_file_path = tempfile.mkstemp(
            suffix=f"_{safe_filename}",
            prefix=SECURITY_CONFIG['TEMP_FILE_PREFIX'],
            dir=temp_dir
        )
        
        try:
            # Stream file content to disk with size checking
            total_size = 0
            with os.fdopen(temp_fd, 'wb') as temp_file:
                while chunk := await file.read(SECURITY_CONFIG['UPLOAD_CHUNK_SIZE']):
                    total_size += len(chunk)
                    if total_size > SECURITY_CONFIG['MAX_FILE_SIZE']:
                        raise APIError(
                            message=f"File too large. Maximum size: {SECURITY_CONFIG['MAX_FILE_SIZE']} bytes",
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            error_code="FILE_TOO_LARGE"
                        )
                    temp_file.write(chunk)
        except APIError:
            raise
        except Exception as e:
            logger.error("Failed to write uploaded file: %s", e)
            raise APIError(
                message="Failed to process uploaded file",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_code="FILE_PROCESSING_ERROR"
            )
        
        # Parse and validate metadata
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
                # Additional metadata validation could be added here
            except json.JSONDecodeError as e:
                raise APIError(
                    message="Invalid metadata JSON format",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error_code="INVALID_METADATA_FORMAT"
                )
        
        # Process audio file
        try:
            memory_data = audio_assistant.process_audio_file(temp_file_path, metadata_dict)
            
            if not memory_data:
                raise APIError(
                    message="No speech detected in audio file",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error_code="NO_SPEECH_DETECTED"
                )
            
            # Convert Memory object to response format
            if isinstance(memory_data, Memory):
                memory_dict = memory_data.dict()
                if isinstance(memory_data.timestamp, datetime):
                    memory_dict["timestamp"] = memory_data.timestamp.timestamp()
                return MemoryResponse(**memory_dict)
            else:
                return MemoryResponse(**memory_data)
                
        except APIError:
            raise
        except Exception as e:
            logger.error("Audio processing failed: %s", e)
            raise APIError(
                message=f"Audio processing failed: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_code="AUDIO_PROCESSING_FAILED"
            )
        
    except APIError:
        raise
    except Exception as e:
        logger.error("Unexpected error in audio upload: %s", e)
        raise APIError(
            message="An unexpected error occurred during file upload",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="UPLOAD_ERROR"
        )
    finally:
        # Guaranteed cleanup of temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.debug("Cleaned up temporary file: %s", temp_file_path)
            except OSError as e:
                logger.error("Failed to cleanup temporary file %s: %s", temp_file_path, e)

# Enhanced CRUD operations with consistent error handling
@app.get("/memories/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str, 
    processor: MemoryProcessor = Depends(get_memory_processor)
):
    """Get a specific memory by ID with validation"""
    try:
        if not memory_id or len(memory_id.strip()) == 0:
            raise APIError(
                message="Memory ID cannot be empty",
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="INVALID_MEMORY_ID"
            )
        
        memory = processor.get_memory(memory_id.strip())
        if not memory:
            raise APIError(
                message="Memory not found",
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="MEMORY_NOT_FOUND"
            )
        
        # Convert Memory object to response format
        if isinstance(memory, Memory):
            memory_dict = memory.dict()
            if isinstance(memory.timestamp, datetime):
                memory_dict["timestamp"] = memory.timestamp.timestamp()
            return MemoryResponse(**memory_dict)
        else:
            return MemoryResponse(**memory)
            
    except APIError:
        raise
    except Exception as e:
        logger.error("Failed to retrieve memory %s: %s", memory_id, e)
        raise APIError(
            message="Failed to retrieve memory",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="MEMORY_RETRIEVAL_FAILED"
        )

@app.get("/memories", response_model=List[MemoryResponse])
async def list_memories(
    skip: int = Query(0, ge=0, description="Number of memories to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of memories to return"),
    processor: MemoryProcessor = Depends(get_memory_processor)
):
    """List memories with pagination and validation"""
    try:
        memories = processor.list_memories(skip=skip, limit=limit)
        
        # Convert Memory objects to response format
        result = []
        for memory in memories:
            if isinstance(memory, Memory):
                memory_dict = memory.dict()
                if isinstance(memory.timestamp, datetime):
                    memory_dict["timestamp"] = memory.timestamp.timestamp()
                result.append(MemoryResponse(**memory_dict))
            else:
                result.append(MemoryResponse(**memory))
        
        return result
        
    except Exception as e:
        logger.error("Failed to list memories: %s", e)
        raise APIError(
            message="Failed to list memories",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="MEMORY_LIST_FAILED"
        )

@app.post("/memories/search", response_model=List[MemoryResponse])
async def search_memories(
    search_req: SearchRequest, 
    processor: MemoryProcessor = Depends(get_memory_processor)
):
    """Search memories with enhanced validation"""
    try:
        # Validate date range
        if search_req.date_from and search_req.date_to:
            if search_req.date_from > search_req.date_to:
                raise APIError(
                    message="date_from must be before date_to",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error_code="INVALID_DATE_RANGE"
                )
        
        memories = processor.search_memories(
            query=search_req.query,
            emotion=search_req.emotion,
            tags=search_req.tags,
            date_from=search_req.date_from,
            date_to=search_req.date_to
        )
        
        # Convert Memory objects to response format
        result = []
        for memory in memories:
            if isinstance(memory, Memory):
                memory_dict = memory.dict()
                if isinstance(memory.timestamp, datetime):
                    memory_dict["timestamp"] = memory.timestamp.timestamp()
                result.append(MemoryResponse(**memory_dict))
            else:
                result.append(MemoryResponse(**memory))
        
        return result
        
    except APIError:
        raise
    except Exception as e:
        logger.error("Search failed: %s", e)
        raise APIError(
            message="Search operation failed",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="SEARCH_FAILED"
        )

# Delete and update operations
@app.delete("/memories/{memory_id}")
async def delete_memory(
    memory_id: str, 
    processor: MemoryProcessor = Depends(get_memory_processor)
):
    """Delete a memory with validation"""
    try:
        if not memory_id or len(memory_id.strip()) == 0:
            raise APIError(
                message="Memory ID cannot be empty",
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="INVALID_MEMORY_ID"
            )
        
        success = processor.delete_memory(memory_id.strip())
        if not success:
            raise APIError(
                message="Memory not found",
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="MEMORY_NOT_FOUND"
            )
        
        return {"message": "Memory deleted successfully", "id": memory_id}
        
    except APIError:
        raise
    except Exception as e:
        logger.error("Failed to delete memory %s: %s", memory_id, e)
        raise APIError(
            message="Failed to delete memory",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="MEMORY_DELETE_FAILED"
        )

@app.put("/memories/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    request: MemoryRequest,
    processor: MemoryProcessor = Depends(get_memory_processor)
):
    """Update a memory with validation"""
    try:
        if not memory_id or len(memory_id.strip()) == 0:
            raise APIError(
                message="Memory ID cannot be empty",
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="INVALID_MEMORY_ID"
            )
        
        memory = processor.update_memory(memory_id.strip(), request.text, request.metadata)
        if not memory:
            raise APIError(
                message="Memory not found",
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="MEMORY_NOT_FOUND"
            )
        
        # Convert Memory object to response format
        if isinstance(memory, Memory):
            memory_dict = memory.dict()
            if isinstance(memory.timestamp, datetime):
                memory_dict["timestamp"] = memory.timestamp.timestamp()
            return MemoryResponse(**memory_dict)
        else:
            return MemoryResponse(**memory)
            
    except APIError:
        raise
    except Exception as e:
        logger.error("Failed to update memory %s: %s", memory_id, e)
        raise APIError(
            message="Failed to update memory",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="MEMORY_UPDATE_FAILED"
        )

# Analytics endpoints with enhanced error handling
@app.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(processor: MemoryProcessor = Depends(get_memory_processor)):
    """Get memory analytics and statistics"""
    try:
        analytics = processor.get_analytics()
        return AnalyticsResponse(**analytics)
    except Exception as e:
        logger.error("Failed to get analytics: %s", e)
        raise APIError(
            message="Failed to retrieve analytics",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="ANALYTICS_FAILED"
        )

@app.get("/analytics/emotions")
async def get_emotion_trends(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    processor: MemoryProcessor = Depends(get_memory_processor)
):
    """Get emotion trends over time"""
    try:
        trends = processor.get_emotion_trends(days)
        return {"trends": trends, "period_days": days}
    except Exception as e:
        logger.error("Failed to get emotion trends: %s", e)
        raise APIError(
            message="Failed to retrieve emotion trends",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="EMOTION_TRENDS_FAILED"
        )

# Export endpoints with security considerations
@app.get("/export/json")
async def export_memories_json(processor: MemoryProcessor = Depends(get_memory_processor)):
    """Export all memories as JSON"""
    try:
        export_data = processor.export_memories("json")
        return {"data": export_data, "format": "json", "exported_at": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error("JSON export failed: %s", e)
        raise APIError(
            message="Export operation failed",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="EXPORT_FAILED"
        )

@app.get("/export/csv")
async def export_memories_csv(processor: MemoryProcessor = Depends(get_memory_processor)):
    """Export all memories as CSV"""
    try:
        csv_data = processor.export_memories("csv")
        return {"data": csv_data, "format": "csv", "exported_at": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error("CSV export failed: %s", e)
        raise APIError(
            message="Export operation failed",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="EXPORT_FAILED"
        )

# Bulk operations with validation
@app.post("/memories/bulk-delete")
async def bulk_delete_memories(
    memory_ids: List[str] = Field(..., min_items=1, max_items=100),
    processor: MemoryProcessor = Depends(get_memory_processor)
):
    """Delete multiple memories with validation"""
    try:
        # Validate memory IDs
        if not memory_ids or len(memory_ids) == 0:
            raise APIError(
                message="Memory IDs list cannot be empty",
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="EMPTY_ID_LIST"
            )
        
        # Clean and validate IDs
        clean_ids = [mid.strip() for mid in memory_ids if mid and mid.strip()]
        if len(clean_ids) != len(memory_ids):
            raise APIError(
                message="Some memory IDs are invalid or empty",
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="INVALID_MEMORY_IDS"
            )
        
        deleted_count = processor.bulk_delete_memories(clean_ids)
        return {
            "message": f"Deleted {deleted_count} out of {len(clean_ids)} memories",
            "deleted_count": deleted_count,
            "requested_count": len(clean_ids)
        }
    except APIError:
        raise
    except Exception as e:
        logger.error("Bulk delete failed: %s", e)
        raise APIError(
            message="Bulk delete operation failed",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="BULK_DELETE_FAILED"
        )

# Vector similarity search with enhanced validation
@app.post("/memories/similar")
async def find_similar_memories(
    request: MemoryRequest,
    limit: int = Query(10, ge=1, le=50, description="Maximum number of similar memories to return"),
    processor: MemoryProcessor = Depends(get_memory_processor)
):
    """Find memories similar to given text"""
    try:
        similar_memories = processor.find_similar_memories(request.text, limit)
        
        # Convert Memory objects to response format
        result = []
        for memory in similar_memories:
            if isinstance(memory, Memory):
                memory_dict = memory.dict()
                if isinstance(memory.timestamp, datetime):
                    memory_dict["timestamp"] = memory.timestamp.timestamp()
                result.append(MemoryResponse(**memory_dict))
            else:
                result.append(MemoryResponse(**memory))
        
        return result
        
    except Exception as e:
        logger.error("Similarity search failed: %s", e)
        raise APIError(
            message="Similarity search failed",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="SIMILARITY_SEARCH_FAILED"
        )

# Application entry point
if __name__ == "__main__":
    import uvicorn
    
    # Configuration for development
    uvicorn_config = {
        "host": "0.0.0.0",
        "port": int(os.getenv("PORT", "8000")),
        "reload": os.getenv("ENVIRONMENT") != "production",
        "log_level": "info",
    }
    
    # Add SSL in production if certificates are available
    if os.getenv("ENVIRONMENT") == "production":
        ssl_keyfile = os.getenv("SSL_KEYFILE")
        ssl_certfile = os.getenv("SSL_CERTFILE")
        if ssl_keyfile and ssl_certfile:
            uvicorn_config.update({
                "ssl_keyfile": ssl_keyfile,
                "ssl_certfile": ssl_certfile
            })
    
    logger.info("Starting Memori API server...")
    uvicorn.run(app, **uvicorn_config)
