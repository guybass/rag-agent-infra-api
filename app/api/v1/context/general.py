from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List

from app.models.index_schemas import (
    GeneralContextRequest,
    GeneralContextResponse,
    ContextSearchRequest,
    ContextSearchResponse,
    ContextSourceType,
)
from app.services.context_service import ContextService
from app.services.multi_vector_store import MultiVectorStoreService
from app.api.deps import verify_api_key_or_token

router = APIRouter()


def get_context_service() -> ContextService:
    return ContextService(MultiVectorStoreService())


@router.post("/", response_model=GeneralContextResponse)
async def store_general_context(
    request: GeneralContextRequest,
    auth: dict = Depends(verify_api_key_or_token),
    context_service: ContextService = Depends(get_context_service),
):
    """
    Store general context information.

    Use this for any contextual information that doesn't fit into
    terraform state or live AWS categories. Examples:
    - Documentation snippets
    - Configuration notes
    - Architecture descriptions
    - Custom metadata
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    result = context_service.store_general_context(
        user_id=user_id,
        content=request.content,
        context_type=request.context_type,
        metadata=request.metadata,
        account_id=request.account_id,
        project_id=request.project_id,
    )

    return result


@router.post("/search", response_model=ContextSearchResponse)
async def search_general_context(
    request: ContextSearchRequest,
    auth: dict = Depends(verify_api_key_or_token),
    context_service: ContextService = Depends(get_context_service),
):
    """
    Search general context semantically.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    results = context_service.search_context(
        user_id=user_id,
        query=request.query,
        account_id=request.account_id,
        source_type=ContextSourceType.GENERAL,
        top_k=request.top_k,
    )

    return ContextSearchResponse(
        results=results,
        query=request.query,
    )


@router.get("/")
async def list_general_context(
    context_type: Optional[str] = Query(None, description="Filter by context type"),
    account_id: Optional[str] = Query(None, description="Filter by account"),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    limit: int = Query(100, ge=1, le=500),
    auth: dict = Depends(verify_api_key_or_token),
    context_service: ContextService = Depends(get_context_service),
):
    """
    List stored general context entries.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    contexts = context_service.get_general_contexts(
        user_id=user_id,
        context_type=context_type,
        account_id=account_id,
        project_id=project_id,
        top_k=limit,
    )

    return {
        "contexts": [
            {
                "context_id": c.context_id,
                "content": c.content,
                "context_type": c.context_type,
                "metadata": c.metadata,
                "indexed_at": c.indexed_at.isoformat(),
            }
            for c in contexts
        ],
        "total": len(contexts),
    }


@router.get("/{context_id}")
async def get_general_context(
    context_id: str,
    auth: dict = Depends(verify_api_key_or_token),
    context_service: ContextService = Depends(get_context_service),
):
    """
    Get a specific general context entry by ID.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    context = context_service.get_general_context_by_id(
        user_id=user_id,
        context_id=context_id,
    )

    if not context:
        raise HTTPException(status_code=404, detail="Context not found")

    return {
        "context_id": context.context_id,
        "content": context.content,
        "context_type": context.context_type,
        "metadata": context.metadata,
        "indexed_at": context.indexed_at.isoformat(),
    }


@router.delete("/{context_id}")
async def delete_general_context(
    context_id: str,
    auth: dict = Depends(verify_api_key_or_token),
    context_service: ContextService = Depends(get_context_service),
):
    """
    Delete a general context entry.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    success = context_service.delete_general_context(
        user_id=user_id,
        context_id=context_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Context not found")

    return {"deleted": True, "context_id": context_id}


@router.post("/batch")
async def store_batch_context(
    contexts: List[GeneralContextRequest],
    auth: dict = Depends(verify_api_key_or_token),
    context_service: ContextService = Depends(get_context_service),
):
    """
    Store multiple general context entries in batch.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    results = []
    for ctx in contexts:
        result = context_service.store_general_context(
            user_id=user_id,
            content=ctx.content,
            context_type=ctx.context_type,
            metadata=ctx.metadata,
            account_id=ctx.account_id,
            project_id=ctx.project_id,
        )
        results.append(result)

    return {
        "stored": len(results),
        "context_ids": [r.context_id for r in results],
    }
