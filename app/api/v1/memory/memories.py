from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List

from app.models.index_schemas import (
    MemoryType,
    MemoryStoreRequest,
    MemorySearchRequest,
    MemoryUpdateImportanceRequest,
    MemoryResponse,
    MemoryListResponse,
    MemorySearchResponse,
)
from app.services.memory_service import MemoryService
from app.services.multi_vector_store import MultiVectorStoreService
from app.api.deps import verify_api_key_or_token

router = APIRouter()


def get_memory_service() -> MemoryService:
    return MemoryService(MultiVectorStoreService())


@router.post("/", response_model=MemoryResponse)
async def store_memory(
    request: MemoryStoreRequest,
    auth: dict = Depends(verify_api_key_or_token),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Store a new memory entry.

    Memory types:
    - session: Tied to a specific session
    - longterm: Persistent across sessions
    - decision: Agent decisions (use /decisions endpoint instead)
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    if request.memory_type == MemoryType.DECISION:
        raise HTTPException(
            status_code=400,
            detail="Use /decisions endpoint for storing decisions",
        )

    memory = memory_service.store_memory(
        user_id=user_id,
        content=request.content,
        memory_type=request.memory_type,
        session_id=request.session_id,
        importance_score=request.importance_score,
        metadata=request.metadata,
        tags=request.tags,
    )

    return MemoryResponse(memory=memory)


@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(
    request: MemorySearchRequest,
    auth: dict = Depends(verify_api_key_or_token),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Search memories semantically.

    Searches across specified memory types with optional filters.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    # Filter out decision type - use /decisions/search for that
    memory_types = [mt for mt in request.memory_types if mt != MemoryType.DECISION]

    results = memory_service.search_memories(
        user_id=user_id,
        query=request.query,
        memory_types=memory_types,
        session_id=request.session_id,
        min_importance=request.min_importance,
        tags=request.tags,
        top_k=request.top_k,
    )

    return MemorySearchResponse(results=results, query=request.query)


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str,
    memory_type: Optional[MemoryType] = Query(None, description="Type hint for faster lookup"),
    auth: dict = Depends(verify_api_key_or_token),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Get a specific memory by ID.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    memory = memory_service.get_memory(user_id, memory_id, memory_type)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    return MemoryResponse(memory=memory)


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    memory_type: Optional[MemoryType] = Query(None, description="Type hint for faster lookup"),
    auth: dict = Depends(verify_api_key_or_token),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Delete a specific memory.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    success = memory_service.delete_memory(user_id, memory_id, memory_type)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")

    return {"message": "Memory deleted", "memory_id": memory_id}


@router.put("/{memory_id}/importance")
async def update_importance(
    memory_id: str,
    request: MemoryUpdateImportanceRequest,
    memory_type: Optional[MemoryType] = Query(None, description="Type hint for faster lookup"),
    auth: dict = Depends(verify_api_key_or_token),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Update memory importance score.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    success = memory_service.update_importance(
        user_id=user_id,
        memory_id=memory_id,
        importance_score=request.importance_score,
        memory_type=memory_type,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")

    return {
        "message": "Importance updated",
        "memory_id": memory_id,
        "new_score": request.importance_score,
    }


@router.post("/{memory_id}/promote", response_model=MemoryResponse)
async def promote_to_longterm(
    memory_id: str,
    auth: dict = Depends(verify_api_key_or_token),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Promote a session memory to long-term storage.

    Only works for session memories.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    memory = memory_service.promote_to_longterm(user_id, memory_id)
    if not memory:
        raise HTTPException(
            status_code=404,
            detail="Memory not found or not a session memory",
        )

    return MemoryResponse(memory=memory)


@router.get("/session/{session_id}", response_model=MemoryListResponse)
async def get_session_memories(
    session_id: str,
    limit: int = Query(50, ge=1, le=500),
    auth: dict = Depends(verify_api_key_or_token),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Get all memories for a specific session.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    memories = memory_service.get_session_memories(
        user_id=user_id,
        session_id=session_id,
        limit=limit,
    )

    return MemoryListResponse(memories=memories, total=len(memories))


@router.delete("/session/{session_id}/cleanup")
async def cleanup_session_memories(
    session_id: str,
    keep_important: bool = Query(True, description="Keep memories above threshold"),
    importance_threshold: float = Query(0.7, ge=0.0, le=1.0),
    auth: dict = Depends(verify_api_key_or_token),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Clean up session memories.

    Important memories can be promoted to long-term storage.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    deleted_count = memory_service.cleanup_session_memories(
        user_id=user_id,
        session_id=session_id,
        keep_important=keep_important,
        importance_threshold=importance_threshold,
    )

    return {
        "message": "Session memories cleaned up",
        "session_id": session_id,
        "deleted_count": deleted_count,
        "kept_important": keep_important,
    }
