from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List

from app.models.index_schemas import (
    UnifiedSearchRequest,
    UnifiedSearchResponse,
    AgentContextRequest,
    AgentContextResponse,
    AllStatsResponse,
    IndexGroup,
)
from app.services.index_group_manager import IndexGroupManager
from app.services.multi_vector_store import MultiVectorStoreService
from app.api.deps import verify_api_key_or_token

router = APIRouter()


def get_index_manager() -> IndexGroupManager:
    return IndexGroupManager(MultiVectorStoreService())


@router.post("/search", response_model=UnifiedSearchResponse)
async def unified_search(
    request: UnifiedSearchRequest,
    auth: dict = Depends(verify_api_key_or_token),
    index_manager: IndexGroupManager = Depends(get_index_manager),
):
    """
    Search across multiple index groups.

    Performs semantic search across terraform, memory, decisions,
    and cloud context indexes. Returns ranked results from each group.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    result = await index_manager.unified_search(
        user_id=user_id,
        query=request.query,
        index_groups=request.index_groups,
        session_id=request.session_id,
        top_k_per_group=request.top_k_per_group,
    )

    return UnifiedSearchResponse(
        results=result,
        query=request.query,
    )


@router.post("/agent-context", response_model=AgentContextResponse)
async def build_agent_context(
    request: AgentContextRequest,
    auth: dict = Depends(verify_api_key_or_token),
    index_manager: IndexGroupManager = Depends(get_index_manager),
):
    """
    Build comprehensive context for an agent.

    Retrieves and formats relevant information from all specified
    index groups for consumption by an AI agent. Respects token
    limits and provides source attribution.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    result = await index_manager.build_agent_context(
        user_id=user_id,
        session_id=request.session_id,
        query=request.query,
        include_groups=request.include_groups,
        max_context_tokens=request.max_context_tokens,
    )

    return AgentContextResponse(
        context=result["context"],
        sources=result["sources"],
        session_id=result["session_id"],
    )


@router.get("/stats", response_model=AllStatsResponse)
async def get_all_stats(
    auth: dict = Depends(verify_api_key_or_token),
    index_manager: IndexGroupManager = Depends(get_index_manager),
):
    """
    Get statistics for all index groups.

    Returns collection counts, document counts, and other
    statistics for terraform, memory, context, and session indexes.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    stats = index_manager.get_all_stats(user_id=user_id)

    return AllStatsResponse(
        stats=stats,
        user_id=user_id,
    )


@router.delete("/cleanup")
async def cleanup_user_data(
    confirm: bool = Query(False, description="Must be true to confirm deletion"),
    auth: dict = Depends(verify_api_key_or_token),
    index_manager: IndexGroupManager = Depends(get_index_manager),
):
    """
    Clean up all data for the current user.

    Deletes all terraform, memory, context, and session data
    associated with the authenticated user. This action is irreversible.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must set confirm=true to delete all user data",
        )

    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    deleted = index_manager.cleanup_user_data(user_id=user_id)

    return {
        "deleted": True,
        "user_id": user_id,
        "counts": deleted,
    }


@router.get("/health")
async def unified_health_check():
    """
    Health check for the unified search service.
    """
    return {
        "status": "healthy",
        "service": "unified-search",
        "index_groups": [g.value for g in IndexGroup],
    }
