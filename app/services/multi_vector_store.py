import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import Optional, Dict, List, Any
import re

from app.config import get_settings


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize metadata dict for ChromaDB storage.
    ChromaDB only accepts: Bool, Int, Float, Str - NOT None.

    Args:
        metadata: Raw metadata dictionary

    Returns:
        Sanitized metadata with None values converted to empty strings
    """
    sanitized = {}
    for key, value in metadata.items():
        if value is None:
            sanitized[key] = ""  # Convert None to empty string
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        elif isinstance(value, list):
            # Convert lists to comma-separated strings
            sanitized[key] = ",".join(str(v) for v in value if v is not None)
        else:
            # Convert other types to string
            sanitized[key] = str(value)
    return sanitized


class MultiVectorStoreService:
    """
    Manages multiple ChromaDB collections with consistent naming
    and metadata handling across index groups.

    Collection naming convention:
    {index_group}__{subindex}__{user_id}__{account_id}__{project_id}

    Examples:
    - terraform__semantic__usr123__acc456__proj789
    - memory__session__usr123
    - memory__longterm__usr123
    - memory__decisions__usr123
    - context__state__usr123__acc456
    - context__live__usr123__acc456
    """

    def __init__(self):
        settings = get_settings()
        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collections_cache: Dict[str, chromadb.Collection] = {}

    def build_collection_name(
        self,
        index_group: str,
        subindex: str,
        user_id: str,
        account_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> str:
        """
        Build standardized collection name.

        Args:
            index_group: terraform, memory, context, etc.
            subindex: semantic, session, longterm, decisions, state, live, etc.
            user_id: User identifier
            account_id: Optional AWS account identifier
            project_id: Optional project identifier

        Returns:
            Standardized collection name
        """
        parts = [index_group, subindex, user_id]
        if account_id:
            parts.append(account_id)
        if project_id:
            parts.append(project_id)
        return "__".join(parts)

    def parse_collection_name(self, collection_name: str) -> Dict[str, str]:
        """
        Parse a collection name into its components.

        Args:
            collection_name: The collection name to parse

        Returns:
            Dictionary with index_group, subindex, user_id, account_id, project_id
        """
        parts = collection_name.split("__")
        result = {
            "index_group": parts[0] if len(parts) > 0 else None,
            "subindex": parts[1] if len(parts) > 1 else None,
            "user_id": parts[2] if len(parts) > 2 else None,
            "account_id": parts[3] if len(parts) > 3 else None,
            "project_id": parts[4] if len(parts) > 4 else None,
        }
        return result

    def get_collection(
        self,
        collection_name: str,
        create_if_missing: bool = True,
    ) -> Optional[chromadb.Collection]:
        """
        Get or create a collection by name.

        Args:
            collection_name: Name of the collection
            create_if_missing: Whether to create the collection if it doesn't exist

        Returns:
            ChromaDB Collection object or None
        """
        if collection_name in self._collections_cache:
            return self._collections_cache[collection_name]

        try:
            if create_if_missing:
                collection = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
            else:
                collection = self.client.get_collection(name=collection_name)

            self._collections_cache[collection_name] = collection
            return collection
        except Exception:
            return None

    def add_documents(
        self,
        collection_name: str,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> int:
        """
        Add documents to a specific collection.

        Args:
            collection_name: Target collection name
            texts: List of text documents
            metadatas: List of metadata dicts
            ids: List of unique IDs

        Returns:
            Number of documents added
        """
        collection = self.get_collection(collection_name)
        if not collection:
            raise ValueError(f"Could not access collection: {collection_name}")

        # Sanitize all metadata to ensure ChromaDB compatibility
        sanitized_metadatas = [sanitize_metadata(m) for m in metadatas]

        collection.add(
            documents=texts,
            metadatas=sanitized_metadatas,
            ids=ids,
        )
        return len(texts)

    def query(
        self,
        collection_name: str,
        query_text: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Query a specific collection with optional filters.

        Args:
            collection_name: Collection to query
            query_text: Query string
            top_k: Number of results to return
            where: Metadata filter
            where_document: Document content filter

        Returns:
            Query results with documents, metadatas, distances
        """
        collection = self.get_collection(collection_name, create_if_missing=False)
        if not collection:
            return {"documents": [], "metadatas": [], "distances": [], "ids": []}

        query_kwargs = {
            "query_texts": [query_text],
            "n_results": top_k,
        }
        if where:
            query_kwargs["where"] = where
        if where_document:
            query_kwargs["where_document"] = where_document

        results = collection.query(**query_kwargs)

        return {
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
            "ids": results["ids"][0] if results["ids"] else [],
        }

    def cross_collection_query(
        self,
        collection_pattern: str,
        query_text: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Query across multiple collections matching a pattern.

        Args:
            collection_pattern: Regex pattern to match collection names
            query_text: Query string
            top_k: Number of results per collection
            where: Metadata filter

        Returns:
            Dictionary mapping collection names to their results
        """
        matching_collections = self.list_collections(pattern=collection_pattern)
        results = {}

        for coll_name in matching_collections:
            coll_results = self.query(
                collection_name=coll_name,
                query_text=query_text,
                top_k=top_k,
                where=where,
            )
            if coll_results["documents"]:
                results[coll_name] = []
                for i in range(len(coll_results["documents"])):
                    results[coll_name].append({
                        "document": coll_results["documents"][i],
                        "metadata": coll_results["metadatas"][i] if coll_results["metadatas"] else {},
                        "distance": coll_results["distances"][i] if coll_results["distances"] else 0,
                        "id": coll_results["ids"][i] if coll_results["ids"] else "",
                    })

        return results

    def get_by_ids(
        self,
        collection_name: str,
        ids: List[str],
    ) -> Dict[str, Any]:
        """
        Get documents by their IDs.

        Args:
            collection_name: Collection to query
            ids: List of document IDs

        Returns:
            Documents with their metadata
        """
        collection = self.get_collection(collection_name, create_if_missing=False)
        if not collection:
            return {"documents": [], "metadatas": [], "ids": []}

        results = collection.get(ids=ids)
        return {
            "documents": results["documents"] or [],
            "metadatas": results["metadatas"] or [],
            "ids": results["ids"] or [],
        }

    def update_documents(
        self,
        collection_name: str,
        ids: List[str],
        texts: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Update existing documents.

        Args:
            collection_name: Collection containing documents
            ids: IDs of documents to update
            texts: New texts (optional)
            metadatas: New metadata (optional)

        Returns:
            True if successful
        """
        collection = self.get_collection(collection_name, create_if_missing=False)
        if not collection:
            return False

        update_kwargs = {"ids": ids}
        if texts:
            update_kwargs["documents"] = texts
        if metadatas:
            # Sanitize metadata to ensure ChromaDB compatibility
            update_kwargs["metadatas"] = [sanitize_metadata(m) for m in metadatas]

        collection.update(**update_kwargs)
        return True

    def delete_documents(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Delete documents from a collection.

        Args:
            collection_name: Collection to delete from
            ids: Specific IDs to delete
            where: Metadata filter for deletion

        Returns:
            True if successful
        """
        collection = self.get_collection(collection_name, create_if_missing=False)
        if not collection:
            return False

        delete_kwargs = {}
        if ids:
            delete_kwargs["ids"] = ids
        if where:
            delete_kwargs["where"] = where

        if not delete_kwargs:
            return False

        collection.delete(**delete_kwargs)
        return True

    def delete_collection(self, collection_name: str) -> bool:
        """
        Delete an entire collection.

        Args:
            collection_name: Collection to delete

        Returns:
            True if successful
        """
        try:
            self.client.delete_collection(name=collection_name)
            if collection_name in self._collections_cache:
                del self._collections_cache[collection_name]
            return True
        except Exception:
            return False

    def list_collections(self, pattern: Optional[str] = None) -> List[str]:
        """
        List all collections, optionally filtered by pattern.

        Args:
            pattern: Regex pattern to filter collection names

        Returns:
            List of collection names
        """
        all_collections = [c.name for c in self.client.list_collections()]

        if pattern:
            regex = re.compile(pattern)
            return [c for c in all_collections if regex.match(c)]

        return all_collections

    def list_collections_for_user(
        self,
        user_id: str,
        index_group: Optional[str] = None,
    ) -> List[str]:
        """
        List all collections for a specific user.

        Args:
            user_id: User identifier
            index_group: Optional filter by index group

        Returns:
            List of collection names
        """
        if index_group:
            pattern = f"^{index_group}__.*__{user_id}(__|$)"
        else:
            pattern = f".*__{user_id}(__|$)"

        return self.list_collections(pattern=pattern)

    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        Get statistics for a collection.

        Args:
            collection_name: Collection name

        Returns:
            Statistics including name and count
        """
        collection = self.get_collection(collection_name, create_if_missing=False)
        if not collection:
            return {"name": collection_name, "count": 0, "exists": False}

        return {
            "name": collection_name,
            "count": collection.count(),
            "exists": True,
        }

    def get_all_stats_for_user(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all collections belonging to a user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary mapping collection names to their stats
        """
        collections = self.list_collections_for_user(user_id)
        return {name: self.get_collection_stats(name) for name in collections}
