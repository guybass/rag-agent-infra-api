from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
from uuid import uuid4

from app.config import get_settings
from app.logging_config import get_logger, setup_logging
from app.api import documents, chat, health
from app.services.vector_store import VectorStoreService
from app.services.multi_vector_store import MultiVectorStoreService
from app.services.session_service import SessionService

# Import new API routers
from app.api.v1.sessions import sessions_router
from app.api.v1.memory import memories_router, decisions_router
from app.api.v1.terraform import files_router as terraform_files_router
from app.api.v1.terraform import search_router as terraform_search_router
from app.api.v1.context import state_router, live_router, general_router
from app.api.v1.unified import search_router as unified_search_router


settings = get_settings()

# Setup logging
logger = setup_logging(
    level="DEBUG" if settings.debug else "INFO",
    json_format=not settings.debug,  # JSON in production, readable in dev
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize services
    vector_store = VectorStoreService()
    multi_vector_store = MultiVectorStoreService()
    session_service = SessionService()

    app.state.vector_store = vector_store
    app.state.multi_vector_store = multi_vector_store
    app.state.session_service = session_service

    yield

    # Shutdown: Cleanup
    await session_service.close()


app = FastAPI(
    title=settings.app_name,
    description="RAG Agent Infrastructure API - Multi-Index Semantic Layer for DevOps/SRE/Platform Engineers",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests and responses."""
    request_id = str(uuid4())[:8]
    start_time = time.time()

    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()

    # Log incoming request
    logger.info(
        f"Request started",
        extra={
            "request_id": request_id,
            "client_ip": client_ip,
            "method": request.method,
            "path": request.url.path,
        }
    )

    try:
        response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)

        # Log response
        log_level = "warning" if response.status_code >= 400 else "info"
        getattr(logger, log_level)(
            f"Request completed",
            extra={
                "request_id": request_id,
                "client_ip": client_ip,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            }
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        return response

    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Request failed: {str(e)}",
            extra={
                "request_id": request_id,
                "client_ip": client_ip,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": duration_ms,
                "error_type": type(e).__name__,
                "error_detail": str(e),
            },
            exc_info=True,
        )
        raise


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions with logging."""
    client_ip = request.client.host if request.client else "unknown"

    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
        extra={
            "client_ip": client_ip,
            "method": request.method,
            "path": request.url.path,
            "error_type": type(exc).__name__,
            "error_detail": str(exc),
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_type": type(exc).__name__,
        },
    )

# Include routers - Core
app.include_router(health.router, tags=["Health"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])

# Include routers - Sessions
app.include_router(sessions_router, prefix="/api/v1/sessions", tags=["Sessions"])

# Include routers - Memory
app.include_router(memories_router, prefix="/api/v1/memory", tags=["Memory"])
app.include_router(decisions_router, prefix="/api/v1/memory/decisions", tags=["Decisions"])

# Include routers - Terraform
app.include_router(terraform_files_router, prefix="/api/v1/terraform/files", tags=["Terraform Files"])
app.include_router(terraform_search_router, prefix="/api/v1/terraform", tags=["Terraform Search"])

# Include routers - Context
app.include_router(state_router, prefix="/api/v1/context/state", tags=["Context State"])
app.include_router(live_router, prefix="/api/v1/context/live", tags=["Context Live"])
app.include_router(general_router, prefix="/api/v1/context/general", tags=["Context General"])

# Include routers - Unified
app.include_router(unified_search_router, prefix="/api/v1/unified", tags=["Unified Search"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
