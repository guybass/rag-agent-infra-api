from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from typing import Optional, List
import io

from app.models.index_schemas import (
    TerraformUploadRequest,
    TerraformUploadResponse,
    TerraformTreeNode,
)
from app.services.terraform.terraform_index_service import TerraformIndexService
from app.services.multi_vector_store import MultiVectorStoreService
from app.api.deps import verify_api_key_or_token
from app.config import get_settings

router = APIRouter()
settings = get_settings()


def get_terraform_service() -> TerraformIndexService:
    return TerraformIndexService(MultiVectorStoreService())


@router.post("/upload", response_model=TerraformUploadResponse)
async def upload_terraform_files(
    files: List[UploadFile] = File(...),
    account_id: str = Form(...),
    project_id: str = Form(...),
    environment: str = Form(default="dev"),
    base_path: str = Form(default=""),
    auth: dict = Depends(verify_api_key_or_token),
    terraform_service: TerraformIndexService = Depends(get_terraform_service),
):
    """
    Upload terraform files to a project.

    Files are stored on the file system and indexed semantically for search.
    Supports .tf and .tfvars files.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    # Validate files
    valid_extensions = {".tf", ".tfvars", ".hcl"}
    file_tuples = []

    for file in files:
        ext = "." + file.filename.split(".")[-1] if "." in file.filename else ""
        if ext.lower() not in valid_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {file.filename}. Only {valid_extensions} allowed.",
            )

        # Check file size
        content = await file.read()
        if len(content) > settings.max_terraform_upload_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=f"File {file.filename} exceeds max size of {settings.max_terraform_upload_size_mb}MB",
            )

        # Build relative path
        relative_path = f"{base_path}/{file.filename}" if base_path else file.filename
        relative_path = relative_path.lstrip("/")

        file_tuples.append((relative_path, io.BytesIO(content)))

    result = terraform_service.upload_terraform_files(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        files=file_tuples,
        environment=environment,
    )

    return result


@router.get("/tree", response_model=TerraformTreeNode)
async def get_file_tree(
    account_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
    depth: int = Query(-1, ge=-1, description="Max depth, -1 for unlimited"),
    auth: dict = Depends(verify_api_key_or_token),
    terraform_service: TerraformIndexService = Depends(get_terraform_service),
):
    """
    Get file tree structure for terraform files.

    Returns a hierarchical view of stored terraform files.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    tree = terraform_service.get_file_tree(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        environment=environment,
        depth=depth,
    )

    return tree


@router.get("/content/{file_path:path}")
async def get_file_content(
    file_path: str,
    account_id: str = Query(...),
    project_id: str = Query(...),
    auth: dict = Depends(verify_api_key_or_token),
    terraform_service: TerraformIndexService = Depends(get_terraform_service),
):
    """
    Get raw content of a terraform file.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    content = terraform_service.get_file_content(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        file_path=file_path,
    )

    if content is None:
        raise HTTPException(status_code=404, detail="File not found")

    return {
        "file_path": file_path,
        "content": content,
        "account_id": account_id,
        "project_id": project_id,
    }


@router.delete("/content/{file_path:path}")
async def delete_file(
    file_path: str,
    account_id: str = Query(...),
    project_id: str = Query(...),
    auth: dict = Depends(verify_api_key_or_token),
    terraform_service: TerraformIndexService = Depends(get_terraform_service),
):
    """
    Delete a terraform file and its index.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    success = terraform_service.delete_file(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        file_path=file_path,
    )

    if not success:
        raise HTTPException(status_code=404, detail="File not found")

    return {
        "message": "File deleted",
        "file_path": file_path,
    }


@router.get("/accounts")
async def list_accounts(
    auth: dict = Depends(verify_api_key_or_token),
    terraform_service: TerraformIndexService = Depends(get_terraform_service),
):
    """
    List all accounts for the user.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))
    accounts = terraform_service.list_accounts(user_id)

    return {"accounts": accounts, "total": len(accounts)}


@router.get("/accounts/{account_id}/projects")
async def list_projects(
    account_id: str,
    auth: dict = Depends(verify_api_key_or_token),
    terraform_service: TerraformIndexService = Depends(get_terraform_service),
):
    """
    List all projects in an account.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))
    projects = terraform_service.list_projects(user_id, account_id)

    return {
        "account_id": account_id,
        "projects": projects,
        "total": len(projects),
    }


@router.get("/stats")
async def get_stats(
    account_id: str = Query(...),
    project_id: str = Query(...),
    auth: dict = Depends(verify_api_key_or_token),
    terraform_service: TerraformIndexService = Depends(get_terraform_service),
):
    """
    Get statistics for a terraform project.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    stats = terraform_service.get_project_stats(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
    )

    return stats


@router.delete("/project")
async def delete_project(
    account_id: str = Query(...),
    project_id: str = Query(...),
    auth: dict = Depends(verify_api_key_or_token),
    terraform_service: TerraformIndexService = Depends(get_terraform_service),
):
    """
    Delete an entire terraform project and its index.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    success = terraform_service.delete_project(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Project not found")

    return {
        "message": "Project deleted",
        "account_id": account_id,
        "project_id": project_id,
    }
