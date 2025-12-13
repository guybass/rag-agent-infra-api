from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List

from app.models.index_schemas import (
    LiveFetchRequest,
    LiveFetchResponse,
    LiveSyncRequest,
    LiveSyncResponse,
    ContextSourceType,
    StateVsLiveComparison,
)
from app.services.context_service import ContextService
from app.services.multi_vector_store import MultiVectorStoreService
from app.api.deps import verify_api_key_or_token

router = APIRouter()


def get_context_service() -> ContextService:
    return ContextService(MultiVectorStoreService())


@router.post("/fetch", response_model=LiveFetchResponse)
async def fetch_live_resources(
    request: LiveFetchRequest,
    auth: dict = Depends(verify_api_key_or_token),
    context_service: ContextService = Depends(get_context_service),
):
    """
    Fetch live resources from AWS APIs.

    Queries AWS directly to get current resource state.
    Optionally indexes the results for future semantic search.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    result = await context_service.fetch_live_resources(
        user_id=user_id,
        account_id=request.account_id,
        region=request.region,
        resource_types=request.resource_types,
        index_results=request.index_results,
        aws_access_key_id=request.aws_access_key_id,
        aws_secret_access_key=request.aws_secret_access_key,
    )

    return result


@router.post("/sync", response_model=LiveSyncResponse)
async def sync_live_state(
    request: LiveSyncRequest,
    auth: dict = Depends(verify_api_key_or_token),
    context_service: ContextService = Depends(get_context_service),
):
    """
    Sync indexed state with live AWS resources.

    Fetches live resources and compares with indexed tfstate data.
    Updates the index with any changes detected.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    result = await context_service.sync_live_state(
        user_id=user_id,
        account_id=request.account_id,
        region=request.region,
        resource_types=request.resource_types,
        aws_access_key_id=request.aws_access_key_id,
        aws_secret_access_key=request.aws_secret_access_key,
    )

    return result


@router.get("/compare/{resource_type}", response_model=StateVsLiveComparison)
async def compare_state_vs_live(
    resource_type: str,
    account_id: str = Query(...),
    region: str = Query("us-east-1"),
    resource_id: Optional[str] = Query(None, description="Specific resource ID to compare"),
    aws_access_key_id: Optional[str] = Query(None),
    aws_secret_access_key: Optional[str] = Query(None),
    auth: dict = Depends(verify_api_key_or_token),
    context_service: ContextService = Depends(get_context_service),
):
    """
    Compare terraform state with live AWS resources.

    Identifies drift between indexed tfstate and actual AWS state.
    Returns resources that exist in one source but not the other,
    and resources with differing configurations.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    result = await context_service.compare_state_vs_live(
        user_id=user_id,
        account_id=account_id,
        region=region,
        resource_type=resource_type,
        resource_id=resource_id,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    return result


@router.get("/resources")
async def list_live_resources(
    account_id: str = Query(...),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    region: Optional[str] = Query(None, description="Filter by region"),
    limit: int = Query(100, ge=1, le=500),
    auth: dict = Depends(verify_api_key_or_token),
    context_service: ContextService = Depends(get_context_service),
):
    """
    List indexed live resources.

    Returns resources previously fetched from AWS and indexed.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    resources = context_service.get_live_resources(
        user_id=user_id,
        account_id=account_id,
        resource_type=resource_type,
        region=region,
        top_k=limit,
    )

    return {
        "resources": [
            {
                "context_id": r.context_id,
                "resource_type": r.resource.resource_type,
                "resource_id": r.resource.resource_id,
                "resource_name": r.resource.resource_name,
                "resource_arn": r.resource.resource_arn,
                "region": r.resource.region,
                "state_data": r.resource.state_data,
                "tags": r.resource.tags,
                "indexed_at": r.indexed_at.isoformat(),
            }
            for r in resources
        ],
        "total": len(resources),
        "account_id": account_id,
    }
