import os
import uuid
import shutil
from datetime import datetime
from typing import Optional, List, Dict, Any, BinaryIO, Tuple
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.multi_vector_store import MultiVectorStoreService
from app.services.terraform.terraform_parser import TerraformParser
from app.models.index_schemas import (
    TerraformHierarchy,
    TerraformMetadata,
    TerraformSearchResult,
    TerraformTreeNode,
    TerraformUploadResponse,
)
from app.config import get_settings


class TerraformIndexService:
    """
    Manages both file-based and semantic indexing of Terraform files.
    Supports hierarchical navigation and semantic search.

    Storage structure:
    {terraform_storage_path}/{user_id}/{account_id}/{project_id}/{environment}/{category}/{resource_kind}/

    Collection naming:
    terraform__semantic__{user_id}__{account_id}__{project_id}
    """

    def __init__(
        self,
        vector_store: Optional[MultiVectorStoreService] = None,
        file_store_base: Optional[str] = None,
    ):
        settings = get_settings()
        self.vector_store = vector_store or MultiVectorStoreService()
        self.file_store_base = file_store_base or settings.terraform_storage_path
        self.parser = TerraformParser()

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.terraform_chunk_size,
            chunk_overlap=settings.terraform_chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )

        # Ensure base directory exists
        os.makedirs(self.file_store_base, exist_ok=True)

    def _get_collection_name(
        self,
        user_id: str,
        account_id: str,
        project_id: str,
    ) -> str:
        """Build collection name for terraform project."""
        return self.vector_store.build_collection_name(
            index_group="terraform",
            subindex="semantic",
            user_id=user_id,
            account_id=account_id,
            project_id=project_id,
        )

    def _get_file_path(
        self,
        user_id: str,
        account_id: str,
        project_id: str,
        relative_path: str = "",
    ) -> str:
        """Build file system path for terraform files."""
        base = Path(self.file_store_base) / user_id / account_id / project_id
        if relative_path:
            return str(base / relative_path)
        return str(base)

    def _metadata_to_dict(self, metadata: TerraformMetadata) -> Dict[str, Any]:
        """Convert TerraformMetadata to dict for ChromaDB."""
        return {
            "user_id": metadata.user_id,
            "account_id": metadata.account_id,
            "project_id": metadata.project_id,
            "environment": metadata.environment,
            "category": metadata.category,
            "resource_kind": metadata.resource_kind,
            "file_type": metadata.file_type,
            "file_path": metadata.file_path,
            "is_module": metadata.is_module,
            "resource_types": ",".join(metadata.resource_types),
            "aws_services": ",".join(metadata.aws_services),
            "module_source": metadata.module_source or "",
            "indexed_at": metadata.indexed_at.isoformat(),
        }

    def _dict_to_metadata(self, d: Dict[str, Any]) -> TerraformMetadata:
        """Convert dict back to TerraformMetadata."""
        return TerraformMetadata(
            user_id=d.get("user_id", ""),
            account_id=d.get("account_id", ""),
            project_id=d.get("project_id", ""),
            environment=d.get("environment", ""),
            category=d.get("category", ""),
            resource_kind=d.get("resource_kind", ""),
            file_type=d.get("file_type", ""),
            file_path=d.get("file_path", ""),
            is_module=d.get("is_module", False),
            resource_types=d.get("resource_types", "").split(",") if d.get("resource_types") else [],
            aws_services=d.get("aws_services", "").split(",") if d.get("aws_services") else [],
            module_source=d.get("module_source") or None,
            indexed_at=datetime.fromisoformat(d["indexed_at"]) if d.get("indexed_at") else datetime.utcnow(),
        )

    # ========================================================================
    # File Operations
    # ========================================================================

    def upload_terraform_files(
        self,
        user_id: str,
        account_id: str,
        project_id: str,
        files: List[Tuple[str, BinaryIO]],
        environment: str = "dev",
    ) -> TerraformUploadResponse:
        """
        Upload and index terraform files.

        Args:
            user_id: User identifier
            account_id: AWS account identifier
            project_id: Project identifier
            files: List of (filename, file_object) tuples
            environment: Environment name

        Returns:
            TerraformUploadResponse with results
        """
        base_path = self._get_file_path(user_id, account_id, project_id)
        os.makedirs(base_path, exist_ok=True)

        collection_name = self._get_collection_name(user_id, account_id, project_id)
        files_processed = 0
        chunks_created = 0
        errors = []

        for filename, file_obj in files:
            try:
                # Determine full path
                file_path = os.path.join(base_path, filename)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                # Save file
                content = file_obj.read()
                if isinstance(content, bytes):
                    content = content.decode("utf-8")

                with open(file_path, "w") as f:
                    f.write(content)

                # Index file
                chunks = self._index_file(
                    user_id=user_id,
                    account_id=account_id,
                    project_id=project_id,
                    file_path=filename,
                    content=content,
                    environment=environment,
                    collection_name=collection_name,
                )

                files_processed += 1
                chunks_created += chunks

            except Exception as e:
                errors.append(f"{filename}: {str(e)}")

        return TerraformUploadResponse(
            files_processed=files_processed,
            chunks_created=chunks_created,
            hierarchy=TerraformHierarchy(
                user_id=user_id,
                account_id=account_id,
                project_id=project_id,
                environment=environment,
            ),
            errors=errors,
        )

    def _index_file(
        self,
        user_id: str,
        account_id: str,
        project_id: str,
        file_path: str,
        content: str,
        environment: str,
        collection_name: str,
    ) -> int:
        """Index a single terraform file."""
        # Parse file
        parse_result = self.parser.parse_file(content, file_path)

        # Extract metadata
        resource_types = [r.resource_type for r in parse_result.resources]
        aws_services = self.parser.get_aws_services(resource_types)
        category = self.parser.determine_category_from_path(file_path) or \
                   (self.parser.get_category_for_resource(resource_types[0]) if resource_types else "unknown")
        resource_kind = self.parser.extract_resource_kind_from_path(file_path) or "general"

        # Auto-detect environment if not in path
        detected_env = self.parser.determine_environment_from_path(file_path)
        final_env = detected_env or environment

        metadata = TerraformMetadata(
            user_id=user_id,
            account_id=account_id,
            project_id=project_id,
            environment=final_env,
            category=category or "unknown",
            resource_kind=resource_kind,
            file_type=parse_result.file_type,
            file_path=file_path,
            is_module=self.parser.is_module_file(file_path),
            resource_types=resource_types,
            aws_services=aws_services,
            module_source=parse_result.module_calls[0].source if parse_result.module_calls else None,
        )

        # Split content into chunks
        chunks = self.text_splitter.split_text(content)

        # Generate IDs and metadatas
        base_id = f"{account_id}_{project_id}_{file_path.replace('/', '_')}"
        ids = [f"{base_id}_{i}" for i in range(len(chunks))]
        metadatas = [self._metadata_to_dict(metadata) for _ in chunks]

        # Add chunk index to each metadata
        for i, meta in enumerate(metadatas):
            meta["chunk_index"] = i
            meta["total_chunks"] = len(chunks)

        # Store in vector store
        self.vector_store.add_documents(
            collection_name=collection_name,
            texts=chunks,
            metadatas=metadatas,
            ids=ids,
        )

        return len(chunks)

    def get_file_tree(
        self,
        user_id: str,
        account_id: Optional[str] = None,
        project_id: Optional[str] = None,
        environment: Optional[str] = None,
        depth: int = -1,
    ) -> TerraformTreeNode:
        """
        Get tree structure of terraform files.

        Args:
            user_id: User identifier
            account_id: Optional account filter
            project_id: Optional project filter
            environment: Optional environment filter
            depth: Maximum depth (-1 for unlimited)

        Returns:
            TerraformTreeNode representing file tree
        """
        base_path = Path(self.file_store_base) / user_id

        if account_id:
            base_path = base_path / account_id
        if project_id:
            base_path = base_path / project_id

        if not base_path.exists():
            return TerraformTreeNode(
                name=user_id,
                path=str(base_path),
                type="directory",
                children=[],
            )

        return self._build_tree_node(base_path, depth)

    def _build_tree_node(
        self,
        path: Path,
        remaining_depth: int,
    ) -> TerraformTreeNode:
        """Recursively build tree node."""
        node = TerraformTreeNode(
            name=path.name,
            path=str(path),
            type="directory" if path.is_dir() else "file",
        )

        if path.is_dir() and remaining_depth != 0:
            for child in sorted(path.iterdir()):
                if child.name.startswith("."):
                    continue
                child_node = self._build_tree_node(
                    child,
                    remaining_depth - 1 if remaining_depth > 0 else -1,
                )
                node.children.append(child_node)

        return node

    def get_file_content(
        self,
        user_id: str,
        account_id: str,
        project_id: str,
        file_path: str,
    ) -> Optional[str]:
        """
        Get raw content of a terraform file.

        Args:
            user_id: User identifier
            account_id: Account identifier
            project_id: Project identifier
            file_path: Relative path to file

        Returns:
            File content or None
        """
        full_path = self._get_file_path(user_id, account_id, project_id, file_path)

        if not os.path.exists(full_path):
            return None

        with open(full_path, "r") as f:
            return f.read()

    def delete_file(
        self,
        user_id: str,
        account_id: str,
        project_id: str,
        file_path: str,
    ) -> bool:
        """
        Delete a terraform file and its index.

        Args:
            user_id: User identifier
            account_id: Account identifier
            project_id: Project identifier
            file_path: Relative path to file

        Returns:
            True if deleted
        """
        full_path = self._get_file_path(user_id, account_id, project_id, file_path)

        if not os.path.exists(full_path):
            return False

        # Delete from file system
        os.remove(full_path)

        # Delete from vector store
        collection_name = self._get_collection_name(user_id, account_id, project_id)
        base_id = f"{account_id}_{project_id}_{file_path.replace('/', '_')}"

        # Delete all chunks for this file
        self.vector_store.delete_documents(
            collection_name=collection_name,
            where={"file_path": file_path},
        )

        return True

    # ========================================================================
    # Semantic Search Operations
    # ========================================================================

    def semantic_search(
        self,
        user_id: str,
        query: str,
        account_id: Optional[str] = None,
        project_id: Optional[str] = None,
        environment: Optional[str] = None,
        category: Optional[str] = None,
        resource_types: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> List[TerraformSearchResult]:
        """
        Semantic search across indexed terraform files.

        Args:
            user_id: User identifier
            query: Search query
            account_id: Optional account filter
            project_id: Optional project filter
            environment: Optional environment filter
            category: Optional category filter
            resource_types: Optional resource type filter
            top_k: Number of results

        Returns:
            List of search results
        """
        # Build where filter
        where = {}
        if environment:
            where["environment"] = environment
        if category:
            where["category"] = category

        results = []

        if account_id and project_id:
            # Search specific project
            collection_name = self._get_collection_name(user_id, account_id, project_id)
            results = self._search_collection(
                collection_name, query, where, resource_types, top_k
            )
        else:
            # Search across all projects
            pattern = f"^terraform__semantic__{user_id}"
            if account_id:
                pattern += f"__{account_id}"

            collections = self.vector_store.list_collections(pattern=pattern)
            for coll_name in collections:
                coll_results = self._search_collection(
                    coll_name, query, where, resource_types, top_k
                )
                results.extend(coll_results)

        # Sort by relevance and limit
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:top_k]

    def _search_collection(
        self,
        collection_name: str,
        query: str,
        where: Dict[str, Any],
        resource_types: Optional[List[str]],
        top_k: int,
    ) -> List[TerraformSearchResult]:
        """Search a single collection."""
        query_results = self.vector_store.query(
            collection_name=collection_name,
            query_text=query,
            top_k=top_k,
            where=where if where else None,
        )

        results = []
        for i, doc in enumerate(query_results["documents"]):
            metadata = query_results["metadatas"][i] if query_results["metadatas"] else {}
            distance = query_results["distances"][i] if query_results["distances"] else 0
            chunk_id = query_results["ids"][i] if query_results["ids"] else ""

            # Filter by resource types if specified
            if resource_types:
                doc_resource_types = metadata.get("resource_types", "").split(",")
                if not any(rt in doc_resource_types for rt in resource_types):
                    continue

            results.append(TerraformSearchResult(
                content=doc,
                metadata=self._dict_to_metadata(metadata),
                relevance_score=1 - distance,
                chunk_id=chunk_id,
            ))

        return results

    def find_resources_by_type(
        self,
        user_id: str,
        resource_type: str,
        account_id: Optional[str] = None,
        project_id: Optional[str] = None,
        top_k: int = 50,
    ) -> List[TerraformSearchResult]:
        """
        Find all resources of a specific type.

        Args:
            user_id: User identifier
            resource_type: Resource type (e.g., "aws_eks_cluster")
            account_id: Optional account filter
            project_id: Optional project filter
            top_k: Maximum results

        Returns:
            List of matching resources
        """
        # Search for the resource type as query
        return self.semantic_search(
            user_id=user_id,
            query=resource_type,
            account_id=account_id,
            project_id=project_id,
            resource_types=[resource_type],
            top_k=top_k,
        )

    # ========================================================================
    # Account/Project Management
    # ========================================================================

    def list_accounts(self, user_id: str) -> List[str]:
        """List all accounts for a user."""
        user_path = Path(self.file_store_base) / user_id
        if not user_path.exists():
            return []

        return [d.name for d in user_path.iterdir() if d.is_dir()]

    def list_projects(self, user_id: str, account_id: str) -> List[str]:
        """List all projects in an account."""
        account_path = Path(self.file_store_base) / user_id / account_id
        if not account_path.exists():
            return []

        return [d.name for d in account_path.iterdir() if d.is_dir()]

    def get_project_stats(
        self,
        user_id: str,
        account_id: str,
        project_id: str,
    ) -> Dict[str, Any]:
        """Get statistics for a project."""
        collection_name = self._get_collection_name(user_id, account_id, project_id)
        coll_stats = self.vector_store.get_collection_stats(collection_name)

        # Count files
        project_path = Path(self._get_file_path(user_id, account_id, project_id))
        file_count = sum(1 for _ in project_path.rglob("*.tf")) if project_path.exists() else 0

        return {
            "user_id": user_id,
            "account_id": account_id,
            "project_id": project_id,
            "indexed_chunks": coll_stats.get("count", 0),
            "file_count": file_count,
            "collection_exists": coll_stats.get("exists", False),
        }

    def delete_project(
        self,
        user_id: str,
        account_id: str,
        project_id: str,
    ) -> bool:
        """Delete an entire project and its index."""
        # Delete files
        project_path = Path(self._get_file_path(user_id, account_id, project_id))
        if project_path.exists():
            shutil.rmtree(project_path)

        # Delete collection
        collection_name = self._get_collection_name(user_id, account_id, project_id)
        return self.vector_store.delete_collection(collection_name)
