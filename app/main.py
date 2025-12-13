from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
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
