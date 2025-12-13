import uuid
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, BinaryIO

from app.services.multi_vector_store import MultiVectorStoreService
from app.services.terraform.terraform_state_parser import TerraformStateParser
from app.services.aws.aws_resource_fetcher import AWSResourceFetcher
from app.models.index_schemas import (
    CloudContext,
    CloudResource,
    ContextSourceType,
    ContextSearchResult,
    StateDiff,
    ContextUploadResponse,
    LiveFetchResponse,
    LiveSyncResponse,
    StateVsLiveComparison,
    GeneralContextResponse,
)
from app.config import get_settings


class ContextService:
    """
    Manages cloud context from terraform state files and live AWS APIs.

    Collection naming:
    - context__state__{user_id}__{account_id}
    - context__live__{user_id}__{account_id}
    - context__general__{user_id}
    """

    def __init__(
        self,
        vector_store: Optional[MultiVectorStoreService] = None,
        aws_fetcher: Optional[AWSResourceFetcher] = None,
    ):
        self.vector_store = vector_store or MultiVectorStoreService()
        self.aws_fetcher = aws_fetcher or AWSResourceFetcher()
        self.state_parser = TerraformStateParser()

    def _get_collection_name(
        self,
        user_id: str,
        account_id: str,
        source_type: str,
    ) -> str:
        """Build collection name for context."""
        return self.vector_store.build_collection_name(
            index_group="context",
            subindex=source_type,
            user_id=user_id,
            account_id=account_id,
        )

    def _get_general_collection_name(self, user_id: str) -> str:
        """Build collection name for general context."""
        return self.vector_store.build_collection_name(
            index_group="context",
            subindex="general",
            user_id=user_id,
        )

    def _context_to_metadata(self, context: CloudContext) -> Dict[str, Any]:
        """Convert CloudContext to metadata dict."""
        return {
            "context_id": context.context_id,
            "user_id": context.user_id,
            "account_id": context.account_id,
            "source_type": context.source_type.value,
            "resource_type": context.resource.resource_type,
            "resource_id": context.resource.resource_id,
            "resource_arn": context.resource.resource_arn or "",
            "resource_name": context.resource.resource_name or "",
            "region": context.resource.region,
            "project_id": context.project_id or "",
            "environment": context.environment or "",
            "indexed_at": context.indexed_at.isoformat(),
            "state_captured_at": context.state_captured_at.isoformat() if context.state_captured_at else "",
        }

    def _metadata_to_context(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> CloudContext:
        """Convert metadata dict back to CloudContext."""
        # Parse state_data from content
        try:
            state_data = json.loads(content)
        except json.JSONDecodeError:
            state_data = {"raw": content}

        return CloudContext(
            context_id=metadata.get("context_id", ""),
            user_id=metadata.get("user_id", ""),
            account_id=metadata.get("account_id", ""),
            source_type=ContextSourceType(metadata.get("source_type", "manual")),
            resource=CloudResource(
                resource_type=metadata.get("resource_type", ""),
                resource_id=metadata.get("resource_id", ""),
                resource_arn=metadata.get("resource_arn") or None,
                resource_name=metadata.get("resource_name") or None,
                region=metadata.get("region", "unknown"),
                state_data=state_data,
            ),
            project_id=metadata.get("project_id") or None,
            environment=metadata.get("environment") or None,
            indexed_at=datetime.fromisoformat(metadata["indexed_at"]) if metadata.get("indexed_at") else datetime.utcnow(),
            state_captured_at=datetime.fromisoformat(metadata["state_captured_at"]) if metadata.get("state_captured_at") else None,
        )

    # ========================================================================
    # State File Operations
    # ========================================================================

    def upload_state_file(
        self,
        user_id: str,
        account_id: str,
        state_content: str,
        project_id: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> ContextUploadResponse:
        """
        Upload and index a terraform.tfstate file.

        Args:
            user_id: User identifier
            account_id: AWS account identifier
            state_content: JSON content of state file
            project_id: Optional project identifier
            environment: Optional environment name

        Returns:
            ContextUploadResponse with results
        """
        # Parse state file
        state_resources = self.state_parser.parse_state_file(state_content)
        cloud_resources = self.state_parser.state_to_cloud_resources(state_resources)

        collection_name = self._get_collection_name(user_id, account_id, "state")
        indexed_count = 0
        errors = []
        now = datetime.utcnow()

        for resource in cloud_resources:
            try:
                context_id = str(uuid.uuid4())

                context = CloudContext(
                    context_id=context_id,
                    user_id=user_id,
                    account_id=account_id,
                    source_type=ContextSourceType.TFSTATE,
                    resource=resource,
                    project_id=project_id,
                    environment=environment,
                    indexed_at=now,
                    state_captured_at=now,
                )

                # Serialize state_data for semantic search
                content = json.dumps(resource.state_data, default=str)

                self.vector_store.add_documents(
                    collection_name=collection_name,
                    texts=[content],
                    metadatas=[self._context_to_metadata(context)],
                    ids=[context_id],
                )

                indexed_count += 1

            except Exception as e:
                errors.append(f"{resource.resource_type}/{resource.resource_id}: {str(e)}")

        return ContextUploadResponse(
            resources_indexed=indexed_count,
            account_id=account_id,
            source_type="tfstate",
            errors=errors,
        )

    def get_state_resources(
        self,
        user_id: str,
        account_id: str,
        resource_type: Optional[str] = None,
        top_k: int = 100,
    ) -> List[CloudContext]:
        """
        List resources from state.

        Args:
            user_id: User identifier
            account_id: Account identifier
            resource_type: Optional filter by type
            top_k: Maximum results

        Returns:
            List of CloudContext objects
        """
        collection_name = self._get_collection_name(user_id, account_id, "state")

        where = {}
        if resource_type:
            where["resource_type"] = resource_type

        results = self.vector_store.query(
            collection_name=collection_name,
            query_text="*",  # Get all
            top_k=top_k,
            where=where if where else None,
        )

        contexts = []
        for i, doc in enumerate(results["documents"]):
            metadata = results["metadatas"][i] if results["metadatas"] else {}
            contexts.append(self._metadata_to_context(doc, metadata))

        return contexts

    # ========================================================================
    # Live AWS Operations
    # ========================================================================

    async def fetch_live_resources(
        self,
        user_id: str,
        account_id: str,
        region: str,
        resource_types: List[str],
        index_results: bool = True,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ) -> LiveFetchResponse:
        """
        Fetch and index live resources from AWS APIs.

        Args:
            user_id: User identifier
            account_id: AWS account identifier
            region: AWS region
            resource_types: Resource types to fetch
            index_results: Whether to index results in ChromaDB
            aws_access_key_id: Optional AWS credentials
            aws_secret_access_key: Optional AWS credentials

        Returns:
            LiveFetchResponse with results
        """
        # Create fetcher with optional credentials
        if aws_access_key_id and aws_secret_access_key:
            fetcher = AWSResourceFetcher(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region=region,
            )
        else:
            fetcher = self.aws_fetcher

        # Fetch resources
        resources_by_type = await fetcher.fetch_all_resources(
            resource_types=resource_types,
            region=region,
        )

        indexed_count = 0
        fetched_count = 0
        type_counts = {}
        errors = []
        now = datetime.utcnow()

        for resource_type, resources in resources_by_type.items():
            type_counts[resource_type] = len(resources)
            fetched_count += len(resources)

            if not index_results:
                continue

            collection_name = self._get_collection_name(user_id, account_id, "live")

            for resource in resources:
                try:
                    context_id = str(uuid.uuid4())

                    context = CloudContext(
                        context_id=context_id,
                        user_id=user_id,
                        account_id=account_id,
                        source_type=ContextSourceType.LIVE_API,
                        resource=resource,
                        indexed_at=now,
                        state_captured_at=now,
                    )

                    content = json.dumps(resource.state_data, default=str)

                    self.vector_store.add_documents(
                        collection_name=collection_name,
                        texts=[content],
                        metadatas=[self._context_to_metadata(context)],
                        ids=[context_id],
                    )

                    indexed_count += 1

                except Exception as e:
                    errors.append(f"{resource.resource_type}/{resource.resource_id}: {str(e)}")

        return LiveFetchResponse(
            resources_fetched=fetched_count,
            resources_indexed=indexed_count,
            resource_types=type_counts,
            account_id=account_id,
            region=region,
            errors=errors,
        )

    async def sync_live_state(
        self,
        user_id: str,
        account_id: str,
        region: str,
        resource_types: Optional[List[str]] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ) -> LiveSyncResponse:
        """
        Sync indexed resources with live AWS state.

        Args:
            user_id: User identifier
            account_id: AWS account identifier
            region: AWS region
            resource_types: Optional filter by types
            aws_access_key_id: Optional AWS credentials
            aws_secret_access_key: Optional AWS credentials

        Returns:
            LiveSyncResponse with sync results
        """
        # Create fetcher with optional credentials
        if aws_access_key_id and aws_secret_access_key:
            fetcher = AWSResourceFetcher(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region=region,
            )
        else:
            fetcher = self.aws_fetcher

        # Get existing live resources
        existing = self.get_live_resources(user_id, account_id, top_k=1000)
        existing_ids = {c.resource.resource_id: c for c in existing}

        # Determine types to fetch
        types_to_fetch = resource_types or list(set(
            c.resource.resource_type.replace("aws_", "")
            for c in existing
        )) or AWSResourceFetcher.SUPPORTED_RESOURCE_TYPES

        # Fetch live resources
        resources_by_type = await fetcher.fetch_all_resources(
            resource_types=types_to_fetch,
            region=region,
        )

        # Track changes
        added = 0
        updated = 0
        removed = 0

        collection_name = self._get_collection_name(user_id, account_id, "live")
        now = datetime.utcnow()

        live_ids = set()

        for resource_type, resources in resources_by_type.items():
            for resource in resources:
                live_ids.add(resource.resource_id)

                if resource.resource_id in existing_ids:
                    # Update existing
                    existing_context = existing_ids[resource.resource_id]
                    context = CloudContext(
                        context_id=existing_context.context_id,
                        user_id=user_id,
                        account_id=account_id,
                        source_type=ContextSourceType.LIVE_API,
                        resource=resource,
                        indexed_at=now,
                        state_captured_at=now,
                    )

                    content = json.dumps(resource.state_data, default=str)

                    self.vector_store.update_documents(
                        collection_name=collection_name,
                        ids=[existing_context.context_id],
                        texts=[content],
                        metadatas=[self._context_to_metadata(context)],
                    )
                    updated += 1
                else:
                    # Add new
                    context_id = str(uuid.uuid4())
                    context = CloudContext(
                        context_id=context_id,
                        user_id=user_id,
                        account_id=account_id,
                        source_type=ContextSourceType.LIVE_API,
                        resource=resource,
                        indexed_at=now,
                        state_captured_at=now,
                    )

                    content = json.dumps(resource.state_data, default=str)

                    self.vector_store.add_documents(
                        collection_name=collection_name,
                        texts=[content],
                        metadatas=[self._context_to_metadata(context)],
                        ids=[context_id],
                    )
                    added += 1

        # Remove stale resources
        for resource_id, context in existing_ids.items():
            if resource_id not in live_ids:
                self.vector_store.delete_documents(
                    collection_name=collection_name,
                    ids=[context.context_id],
                )
                removed += 1

        unchanged = len(existing_ids) - updated - removed

        return LiveSyncResponse(
            synced=added + updated,
            added=added,
            updated=updated,
            removed=removed,
            unchanged=max(0, unchanged),
            account_id=account_id,
            region=region,
            errors=[],
        )

    def get_live_resources(
        self,
        user_id: str,
        account_id: str,
        resource_type: Optional[str] = None,
        region: Optional[str] = None,
        top_k: int = 100,
    ) -> List[CloudContext]:
        """
        List cached live resources.

        Args:
            user_id: User identifier
            account_id: Account identifier
            resource_type: Optional filter by type
            region: Optional filter by region
            top_k: Maximum results

        Returns:
            List of CloudContext objects
        """
        collection_name = self._get_collection_name(user_id, account_id, "live")

        where = {}
        if resource_type:
            where["resource_type"] = resource_type
        if region:
            where["region"] = region

        results = self.vector_store.query(
            collection_name=collection_name,
            query_text="*",
            top_k=top_k,
            where=where if where else None,
        )

        contexts = []
        for i, doc in enumerate(results["documents"]):
            metadata = results["metadatas"][i] if results["metadatas"] else {}
            contexts.append(self._metadata_to_context(doc, metadata))

        return contexts

    # ========================================================================
    # Search Operations
    # ========================================================================

    def search_context(
        self,
        user_id: str,
        query: str,
        account_id: Optional[str] = None,
        source_type: Optional[ContextSourceType] = None,
        resource_types: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> List[ContextSearchResult]:
        """
        Search cloud context semantically.

        Args:
            user_id: User identifier
            query: Search query
            account_id: Optional account filter
            source_type: Optional source filter (state or live)
            resource_types: Optional resource type filter
            top_k: Number of results

        Returns:
            List of search results
        """
        all_results = []

        # Determine which collections to search
        if account_id:
            if source_type:
                collections = [self._get_collection_name(user_id, account_id, source_type.value.replace("_api", ""))]
            else:
                collections = [
                    self._get_collection_name(user_id, account_id, "state"),
                    self._get_collection_name(user_id, account_id, "live"),
                ]
        else:
            # Search all accounts
            pattern = f"^context__(state|live)__{user_id}"
            collections = self.vector_store.list_collections(pattern=pattern)

        for collection_name in collections:
            where = {}
            if resource_types:
                # ChromaDB doesn't support IN operator, so filter post-query
                pass

            results = self.vector_store.query(
                collection_name=collection_name,
                query_text=query,
                top_k=top_k,
                where=where if where else None,
            )

            for i, doc in enumerate(results["documents"]):
                metadata = results["metadatas"][i] if results["metadatas"] else {}
                distance = results["distances"][i] if results["distances"] else 0

                # Filter by resource type if specified
                if resource_types and metadata.get("resource_type") not in resource_types:
                    continue

                context = self._metadata_to_context(doc, metadata)
                all_results.append(ContextSearchResult(
                    context=context,
                    relevance_score=1 - distance,
                ))

        # Sort by relevance
        all_results.sort(key=lambda x: x.relevance_score, reverse=True)
        return all_results[:top_k]

    async def compare_state_vs_live(
        self,
        user_id: str,
        account_id: str,
        region: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ) -> StateVsLiveComparison:
        """
        Compare terraform state with live AWS state.

        Args:
            user_id: User identifier
            account_id: Account identifier
            region: AWS region
            resource_type: Resource type to compare
            resource_id: Optional specific resource ID
            aws_access_key_id: Optional AWS credentials
            aws_secret_access_key: Optional AWS credentials

        Returns:
            StateVsLiveComparison with differences
        """
        # Get state resources
        state_resources = self.get_state_resources(
            user_id=user_id,
            account_id=account_id,
            resource_type=resource_type,
            top_k=500,
        )

        # Get live resources (fetch fresh if credentials provided)
        if aws_access_key_id and aws_secret_access_key:
            fetcher = AWSResourceFetcher(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region=region,
            )
            # Map resource type to fetcher type
            rt_short = resource_type.replace("aws_", "")
            resources_by_type = await fetcher.fetch_all_resources([rt_short], region)
            live_resources = resources_by_type.get(rt_short, [])
            live_contexts = [
                CloudContext(
                    context_id=str(uuid.uuid4()),
                    user_id=user_id,
                    account_id=account_id,
                    source_type=ContextSourceType.LIVE_API,
                    resource=r,
                    indexed_at=datetime.utcnow(),
                )
                for r in live_resources
            ]
        else:
            live_contexts = self.get_live_resources(
                user_id=user_id,
                account_id=account_id,
                resource_type=resource_type,
                region=region,
                top_k=500,
            )

        # Build lookup maps
        state_by_id = {c.resource.resource_id: c for c in state_resources}
        live_by_id = {c.resource.resource_id: c for c in live_contexts}

        state_only = []
        live_only = []
        differences = []
        matched = 0

        # Find resources only in state
        for rid, ctx in state_by_id.items():
            if resource_id and rid != resource_id:
                continue
            if rid not in live_by_id:
                state_only.append({
                    "resource_id": rid,
                    "resource_type": ctx.resource.resource_type,
                    "resource_name": ctx.resource.resource_name,
                    "state_data": ctx.resource.state_data,
                })
            else:
                # Compare
                live_ctx = live_by_id[rid]
                state_data = ctx.resource.state_data
                live_data = live_ctx.resource.state_data

                diffs = []
                all_keys = set(state_data.keys()) | set(live_data.keys())
                for key in all_keys:
                    if state_data.get(key) != live_data.get(key):
                        diffs.append({
                            "key": key,
                            "state_value": state_data.get(key),
                            "live_value": live_data.get(key),
                        })

                if diffs:
                    differences.append(StateDiff(
                        resource_id=rid,
                        resource_type=ctx.resource.resource_type,
                        state_value=state_data,
                        live_value=live_data,
                        differences=diffs,
                        drift_detected=True,
                    ))
                else:
                    matched += 1

        # Find resources only in live
        for rid, ctx in live_by_id.items():
            if resource_id and rid != resource_id:
                continue
            if rid not in state_by_id:
                live_only.append({
                    "resource_id": rid,
                    "resource_type": ctx.resource.resource_type,
                    "resource_name": ctx.resource.resource_name,
                    "state_data": ctx.resource.state_data,
                })

        return StateVsLiveComparison(
            resource_type=resource_type,
            account_id=account_id,
            region=region,
            state_only=state_only,
            live_only=live_only,
            differences=differences,
            matched=matched,
            drift_detected=len(state_only) > 0 or len(live_only) > 0 or len(differences) > 0,
        )

    # ========================================================================
    # General Context Operations
    # ========================================================================

    def store_general_context(
        self,
        user_id: str,
        content: str,
        context_type: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
        account_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> GeneralContextResponse:
        """
        Store general context information.

        Args:
            user_id: User identifier
            content: Context content
            context_type: Type of context
            metadata: Additional metadata
            account_id: Optional account ID
            project_id: Optional project ID

        Returns:
            GeneralContextResponse
        """
        collection_name = self._get_general_collection_name(user_id)
        context_id = str(uuid.uuid4())
        now = datetime.utcnow()

        meta = {
            "context_id": context_id,
            "user_id": user_id,
            "context_type": context_type,
            "account_id": account_id or "",
            "project_id": project_id or "",
            "indexed_at": now.isoformat(),
        }

        if metadata:
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    meta[f"custom_{k}"] = v

        self.vector_store.add_documents(
            collection_name=collection_name,
            texts=[content],
            metadatas=[meta],
            ids=[context_id],
        )

        return GeneralContextResponse(
            context_id=context_id,
            indexed_at=now,
        )

    def search_general_context(
        self,
        user_id: str,
        query: str,
        context_type: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search general context.

        Args:
            user_id: User identifier
            query: Search query
            context_type: Optional filter by type
            top_k: Number of results

        Returns:
            List of context entries
        """
        collection_name = self._get_general_collection_name(user_id)

        where = {}
        if context_type:
            where["context_type"] = context_type

        results = self.vector_store.query(
            collection_name=collection_name,
            query_text=query,
            top_k=top_k,
            where=where if where else None,
        )

        output = []
        for i, doc in enumerate(results["documents"]):
            metadata = results["metadatas"][i] if results["metadatas"] else {}
            distance = results["distances"][i] if results["distances"] else 0

            output.append({
                "content": doc,
                "metadata": metadata,
                "relevance_score": 1 - distance,
            })

        return output

    def get_general_contexts(
        self,
        user_id: str,
        context_type: Optional[str] = None,
        account_id: Optional[str] = None,
        project_id: Optional[str] = None,
        top_k: int = 100,
    ) -> List[Any]:
        """
        List general context entries.

        Args:
            user_id: User identifier
            context_type: Optional filter by type
            account_id: Optional filter by account
            project_id: Optional filter by project
            top_k: Maximum results

        Returns:
            List of context entries as objects with context_id, content, etc.
        """
        collection_name = self._get_general_collection_name(user_id)

        where = {}
        if context_type:
            where["context_type"] = context_type
        if account_id:
            where["account_id"] = account_id
        if project_id:
            where["project_id"] = project_id

        results = self.vector_store.query(
            collection_name=collection_name,
            query_text="*",
            top_k=top_k,
            where=where if where else None,
        )

        class GeneralContext:
            def __init__(self, context_id, content, context_type, metadata, indexed_at):
                self.context_id = context_id
                self.content = content
                self.context_type = context_type
                self.metadata = metadata
                self.indexed_at = indexed_at

        output = []
        for i, doc in enumerate(results["documents"]):
            metadata = results["metadatas"][i] if results["metadatas"] else {}

            # Extract custom metadata
            custom_meta = {}
            for k, v in metadata.items():
                if k.startswith("custom_"):
                    custom_meta[k[7:]] = v

            indexed_at = datetime.fromisoformat(metadata["indexed_at"]) if metadata.get("indexed_at") else datetime.utcnow()

            output.append(GeneralContext(
                context_id=metadata.get("context_id", ""),
                content=doc,
                context_type=metadata.get("context_type", "general"),
                metadata=custom_meta,
                indexed_at=indexed_at,
            ))

        return output

    def get_general_context_by_id(
        self,
        user_id: str,
        context_id: str,
    ) -> Optional[Any]:
        """
        Get a specific general context entry by ID.

        Args:
            user_id: User identifier
            context_id: Context ID

        Returns:
            Context entry or None
        """
        collection_name = self._get_general_collection_name(user_id)

        results = self.vector_store.query(
            collection_name=collection_name,
            query_text="*",
            top_k=1,
            where={"context_id": context_id},
        )

        if not results["documents"]:
            return None

        metadata = results["metadatas"][0] if results["metadatas"] else {}

        class GeneralContext:
            def __init__(self, context_id, content, context_type, metadata, indexed_at):
                self.context_id = context_id
                self.content = content
                self.context_type = context_type
                self.metadata = metadata
                self.indexed_at = indexed_at

        # Extract custom metadata
        custom_meta = {}
        for k, v in metadata.items():
            if k.startswith("custom_"):
                custom_meta[k[7:]] = v

        indexed_at = datetime.fromisoformat(metadata["indexed_at"]) if metadata.get("indexed_at") else datetime.utcnow()

        return GeneralContext(
            context_id=metadata.get("context_id", context_id),
            content=results["documents"][0],
            context_type=metadata.get("context_type", "general"),
            metadata=custom_meta,
            indexed_at=indexed_at,
        )

    def delete_general_context(
        self,
        user_id: str,
        context_id: str,
    ) -> bool:
        """
        Delete a general context entry.

        Args:
            user_id: User identifier
            context_id: Context ID to delete

        Returns:
            True if deleted, False if not found
        """
        collection_name = self._get_general_collection_name(user_id)

        # Check if exists
        existing = self.get_general_context_by_id(user_id, context_id)
        if not existing:
            return False

        self.vector_store.delete_documents(
            collection_name=collection_name,
            ids=[context_id],
        )

        return True
