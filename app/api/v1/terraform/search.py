from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List

from app.models.index_schemas import (
    TerraformSearchRequest,
    TerraformSearchResult,
)
from app.services.terraform.terraform_index_service import TerraformIndexService
from app.services.multi_vector_store import MultiVectorStoreService
from app.api.deps import verify_api_key_or_token

router = APIRouter()


def get_terraform_service() -> TerraformIndexService:
    return TerraformIndexService(MultiVectorStoreService())


@router.post("/search")
async def search_terraform(
    request: TerraformSearchRequest,
    auth: dict = Depends(verify_api_key_or_token),
    terraform_service: TerraformIndexService = Depends(get_terraform_service),
):
    """
    Semantic search across terraform files.

    Supports filtering by:
    - Account and project
    - Environment (dev, staging, prod)
    - Category (networking, compute, etc.)
    - Resource types (aws_eks_cluster, aws_vpc, etc.)
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    # Extract hierarchy filters
    account_id = request.hierarchy.account_id if request.hierarchy else None
    project_id = request.hierarchy.project_id if request.hierarchy else None
    environment = request.hierarchy.environment if request.hierarchy else None

    # Get first category and environment from lists if provided
    category = request.categories[0] if request.categories else None
    if not environment and request.environments:
        environment = request.environments[0]

    results = terraform_service.semantic_search(
        user_id=user_id,
        query=request.query,
        account_id=account_id,
        project_id=project_id,
        environment=environment,
        category=category,
        resource_types=request.resource_types,
        top_k=request.top_k,
    )

    # Optionally include full file content
    if request.include_file_content:
        for result in results:
            content = terraform_service.get_file_content(
                user_id=user_id,
                account_id=result.metadata.account_id,
                project_id=result.metadata.project_id,
                file_path=result.metadata.file_path,
            )
            if content:
                result.content = content

    return {
        "results": [
            {
                "content": r.content,
                "metadata": {
                    "account_id": r.metadata.account_id,
                    "project_id": r.metadata.project_id,
                    "environment": r.metadata.environment,
                    "category": r.metadata.category,
                    "resource_kind": r.metadata.resource_kind,
                    "file_type": r.metadata.file_type,
                    "file_path": r.metadata.file_path,
                    "is_module": r.metadata.is_module,
                    "resource_types": r.metadata.resource_types,
                    "aws_services": r.metadata.aws_services,
                },
                "relevance_score": r.relevance_score,
                "chunk_id": r.chunk_id,
            }
            for r in results
        ],
        "query": request.query,
        "total": len(results),
    }


@router.get("/resources")
async def find_resources(
    resource_type: str = Query(..., description="Resource type (e.g., aws_eks_cluster)"),
    account_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    top_k: int = Query(50, ge=1, le=200),
    auth: dict = Depends(verify_api_key_or_token),
    terraform_service: TerraformIndexService = Depends(get_terraform_service),
):
    """
    Find all resources of a specific type.

    Examples:
    - aws_eks_cluster
    - aws_vpc
    - aws_security_group
    - aws_rds_instance
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    results = terraform_service.find_resources_by_type(
        user_id=user_id,
        resource_type=resource_type,
        account_id=account_id,
        project_id=project_id,
        top_k=top_k,
    )

    return {
        "resource_type": resource_type,
        "results": [
            {
                "content": r.content,
                "file_path": r.metadata.file_path,
                "account_id": r.metadata.account_id,
                "project_id": r.metadata.project_id,
                "environment": r.metadata.environment,
                "relevance_score": r.relevance_score,
            }
            for r in results
        ],
        "total": len(results),
    }


@router.get("/modules")
async def list_modules(
    account_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None, description="Filter by category (networking, compute, etc.)"),
    auth: dict = Depends(verify_api_key_or_token),
    terraform_service: TerraformIndexService = Depends(get_terraform_service),
):
    """
    List available modules.

    Returns modules found in the terraform files with their locations.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    # Search for module definitions
    results = terraform_service.semantic_search(
        user_id=user_id,
        query="module source",
        account_id=account_id,
        project_id=project_id,
        category=category,
        top_k=100,
    )

    # Extract unique modules
    modules = {}
    for r in results:
        if r.metadata.is_module and r.metadata.module_source:
            key = f"{r.metadata.account_id}/{r.metadata.project_id}/{r.metadata.file_path}"
            if key not in modules:
                modules[key] = {
                    "file_path": r.metadata.file_path,
                    "account_id": r.metadata.account_id,
                    "project_id": r.metadata.project_id,
                    "category": r.metadata.category,
                    "resource_kind": r.metadata.resource_kind,
                }

    return {
        "modules": list(modules.values()),
        "total": len(modules),
    }
