from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.models.index_schemas import (
    DecisionStoreRequest,
    DecisionSearchRequest,
    DecisionResponse,
    DecisionListResponse,
    DecisionSearchResponse,
)
from app.services.memory_service import MemoryService
from app.services.multi_vector_store import MultiVectorStoreService
from app.api.deps import verify_api_key_or_token

router = APIRouter()


def get_memory_service() -> MemoryService:
    return MemoryService(MultiVectorStoreService())


@router.post("/", response_model=DecisionResponse)
async def store_decision(
    request: DecisionStoreRequest,
    auth: dict = Depends(verify_api_key_or_token),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Store an agent decision.

    Decisions are indexed for semantic search and can be retrieved
    by related resources, decision type, or semantic similarity.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    decision = memory_service.store_decision(
        user_id=user_id,
        session_id=request.session_id,
        decision_type=request.decision_type,
        context=request.context,
        reasoning=request.reasoning,
        outcome=request.outcome,
        confidence_score=request.confidence_score,
        related_resources=request.related_resources,
        tags=request.tags,
    )

    return DecisionResponse(decision=decision)


@router.post("/search", response_model=DecisionSearchResponse)
async def search_decisions(
    request: DecisionSearchRequest,
    auth: dict = Depends(verify_api_key_or_token),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Search past agent decisions semantically.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    results = memory_service.search_decisions(
        user_id=user_id,
        query=request.query,
        decision_type=request.decision_type,
        session_id=request.session_id,
        min_confidence=request.min_confidence,
        top_k=request.top_k,
    )

    return DecisionSearchResponse(results=results, query=request.query)


@router.get("/{decision_id}", response_model=DecisionResponse)
async def get_decision(
    decision_id: str,
    auth: dict = Depends(verify_api_key_or_token),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Get a specific decision by ID.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    decision = memory_service.get_decision(user_id, decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    return DecisionResponse(decision=decision)


@router.get("/resource/{resource_id}", response_model=DecisionListResponse)
async def get_decisions_for_resource(
    resource_id: str,
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_api_key_or_token),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Get all decisions related to a specific resource.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    decisions = memory_service.get_decisions_for_resource(
        user_id=user_id,
        resource_id=resource_id,
        top_k=limit,
    )

    return DecisionListResponse(decisions=decisions, total=len(decisions))
