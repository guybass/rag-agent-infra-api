import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import Optional
import uuid

from app.config import get_settings


class VectorStoreService:
    """Service for managing ChromaDB vector store operations."""

    def __init__(self):
        settings = get_settings()

        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        self.collection = self.client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(
        self,
        texts: list[str],
        metadatas: list[dict],
        document_id: str,
    ) -> int:
        """
        Add document chunks to the vector store.

        Args:
            texts: List of text chunks
            metadatas: List of metadata dicts for each chunk
            document_id: Parent document ID

        Returns:
            Number of chunks added
        """
        ids = [f"{document_id}_{i}" for i in range(len(texts))]

        # Add document_id to each metadata
        for metadata in metadatas:
            metadata["document_id"] = document_id

        self.collection.add(
            documents=texts,
            metadatas=metadatas,
            ids=ids,
        )

        return len(texts)

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        filter_metadata: Optional[dict] = None,
    ) -> dict:
        """
        Query the vector store for similar documents.

        Args:
            query_text: The query string
            top_k: Number of results to return
            filter_metadata: Optional metadata filter

        Returns:
            Query results with documents, metadatas, and distances
        """
        query_kwargs = {
            "query_texts": [query_text],
            "n_results": top_k,
        }

        if filter_metadata:
            query_kwargs["where"] = filter_metadata

        results = self.collection.query(**query_kwargs)

        return {
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
        }

    def delete_document(self, document_id: str) -> bool:
        """
        Delete all chunks belonging to a document.

        Args:
            document_id: The document ID to delete

        Returns:
            True if successful
        """
        self.collection.delete(where={"document_id": document_id})
        return True

    def get_document_ids(self) -> list[str]:
        """Get all unique document IDs in the collection."""
        results = self.collection.get()
        if not results["metadatas"]:
            return []

        document_ids = set()
        for metadata in results["metadatas"]:
            if "document_id" in metadata:
                document_ids.add(metadata["document_id"])

        return list(document_ids)

    def get_document_metadata(self, document_id: str) -> Optional[dict]:
        """Get metadata for a specific document."""
        results = self.collection.get(
            where={"document_id": document_id},
            limit=1,
        )

        if results["metadatas"]:
            return results["metadatas"][0]
        return None

    def get_collection_stats(self) -> dict:
        """Get statistics about the collection."""
        return {
            "name": self.collection.name,
            "count": self.collection.count(),
        }
