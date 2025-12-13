from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from typing import Optional, List

from app.models.index_schemas import (
    ContextUploadResponse,
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


@router.post("/upload", response_model=ContextUploadResponse)
async def upload_state_file(
    file: UploadFile = File(...),
    account_id: str = Form(...),
    project_id: Optional[str] = Form(None),
    environment: Optional[str] = Form(None),
    auth: dict = Depends(verify_api_key_or_token),
    context_service: ContextService = Depends(get_context_service),
):
    """
    Upload and index a terraform.tfstate file.

    Parses the state file and indexes all resources for semantic search.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    # Validate file
    if not file.filename.endswith((".tfstate", ".json")):
        raise HTTPException(
            status_code=400,
            detail="File must be a .tfstate or .json file",
        )

    content = await file.read()
    try:
        state_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding")

    result = context_service.upload_state_file(
        user_id=user_id,
        account_id=account_id,
        state_content=state_content,
        project_id=project_id,
        environment=environment,
    )

    return result


@router.get("/resources")
async def list_state_resources(
    account_id: str = Query(...),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    limit: int = Query(100, ge=1, le=500),
    auth: dict = Depends(verify_api_key_or_token),
    context_service: ContextService = Depends(get_context_service),
):
    """
    List resources from terraform state.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    resources = context_service.get_state_resources(
        user_id=user_id,
        account_id=account_id,
        resource_type=resource_type,
        top_k=limit,
    )

    return {
        "resources": [
            {
                "context_id": r.context_id,
                "resource_type": r.resource.resource_type,
                "resource_id": r.resource.resource_id,
                "resource_name": r.resource.resource_name,
                "region": r.resource.region,
                "state_data": r.resource.state_data,
                "indexed_at": r.indexed_at.isoformat(),
            }
            for r in resources
        ],
        "total": len(resources),
        "account_id": account_id,
    }


@router.post("/search", response_model=ContextSearchResponse)
async def search_state(
    request: ContextSearchRequest,
    auth: dict = Depends(verify_api_key_or_token),
    context_service: ContextService = Depends(get_context_service),
):
    """
    Search terraform state resources semantically.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    results = context_service.search_context(
        user_id=user_id,
        query=request.query,
        account_id=request.account_id,
        source_type=ContextSourceType.TFSTATE,
        resource_types=request.resource_types,
        top_k=request.top_k,
    )

    return ContextSearchResponse(
        results=results,
        query=request.query,
    )
