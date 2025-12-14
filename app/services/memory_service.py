import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.services.multi_vector_store import MultiVectorStoreService
from app.models.index_schemas import (
    MemoryEntry,
    MemoryType,
    AgentDecision,
    MemorySearchResult,
    DecisionSearchResult,
)
from app.config import get_settings


class MemoryService:
    """
    Manages persistent memory across sessions with semantic search.
    Supports session-specific, long-term, and decision memories.

    Collection naming:
    - memory__session__{user_id}
    - memory__longterm__{user_id}
    - memory__decisions__{user_id}
    """

    def __init__(self, vector_store: Optional[MultiVectorStoreService] = None):
        self.vector_store = vector_store or MultiVectorStoreService()
        settings = get_settings()
        self.chunk_size = settings.memory_chunk_size
        self.chunk_overlap = settings.memory_chunk_overlap

    def _get_collection_name(self, user_id: str, memory_type: MemoryType) -> str:
        """Build collection name for memory type."""
        return self.vector_store.build_collection_name(
            index_group="memory",
            subindex=memory_type.value,
            user_id=user_id,
        )

    def _memory_to_metadata(self, memory: MemoryEntry) -> Dict[str, Any]:
        """Convert memory entry to metadata dict for ChromaDB."""
        return {
            "memory_id": memory.memory_id,
            "user_id": memory.user_id or "",
            "session_id": memory.session_id or "",
            "memory_type": memory.memory_type.value,
            "importance_score": memory.importance_score,
            "tags": ",".join(memory.tags) if memory.tags else "",
            "created_at": memory.created_at.isoformat(),
            "accessed_at": memory.accessed_at.isoformat(),
            "access_count": memory.access_count,
        }

    def _metadata_to_memory(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> MemoryEntry:
        """Convert metadata dict back to MemoryEntry."""
        return MemoryEntry(
            memory_id=metadata.get("memory_id", ""),
            user_id=metadata.get("user_id", ""),
            session_id=metadata.get("session_id") or None,
            memory_type=MemoryType(metadata.get("memory_type", "session")),
            content=content,
            importance_score=float(metadata.get("importance_score", 0.5)),
            tags=metadata.get("tags", "").split(",") if metadata.get("tags") else [],
            created_at=datetime.fromisoformat(metadata["created_at"]) if metadata.get("created_at") else datetime.utcnow(),
            accessed_at=datetime.fromisoformat(metadata["accessed_at"]) if metadata.get("accessed_at") else datetime.utcnow(),
            access_count=int(metadata.get("access_count", 0)),
        )

    def store_memory(
        self,
        user_id: str,
        content: str,
        memory_type: MemoryType,
        session_id: Optional[str] = None,
        importance_score: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> MemoryEntry:
        """
        Store a new memory entry.

        Args:
            user_id: User identifier
            content: Memory content
            memory_type: Type of memory (session, longterm, decision)
            session_id: Optional session ID for session memories
            importance_score: Importance score (0.0 to 1.0)
            metadata: Additional metadata
            tags: Tags for categorization

        Returns:
            Created MemoryEntry
        """
        memory_id = str(uuid.uuid4())
        now = datetime.utcnow()

        memory = MemoryEntry(
            memory_id=memory_id,
            user_id=user_id,
            session_id=session_id,
            memory_type=memory_type,
            content=content,
            metadata=metadata or {},
            importance_score=importance_score,
            tags=tags or [],
            created_at=now,
            accessed_at=now,
            access_count=0,
        )

        collection_name = self._get_collection_name(user_id, memory_type)
        mem_metadata = self._memory_to_metadata(memory)

        # Add any custom metadata
        if metadata:
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    mem_metadata[f"custom_{k}"] = v

        self.vector_store.add_documents(
            collection_name=collection_name,
            texts=[content],
            metadatas=[mem_metadata],
            ids=[memory_id],
        )

        return memory

    def get_memory(
        self,
        user_id: str,
        memory_id: str,
        memory_type: Optional[MemoryType] = None,
    ) -> Optional[MemoryEntry]:
        """
        Get a specific memory by ID.

        Args:
            user_id: User identifier
            memory_id: Memory identifier
            memory_type: Optional type hint for faster lookup

        Returns:
            MemoryEntry if found
        """
        types_to_check = [memory_type] if memory_type else list(MemoryType)

        for mtype in types_to_check:
            collection_name = self._get_collection_name(user_id, mtype)
            results = self.vector_store.get_by_ids(collection_name, [memory_id])

            if results["documents"]:
                # Update access count
                memory = self._metadata_to_memory(
                    results["documents"][0],
                    results["metadatas"][0],
                )
                memory.accessed_at = datetime.utcnow()
                memory.access_count += 1

                # Update in store
                self.vector_store.update_documents(
                    collection_name=collection_name,
                    ids=[memory_id],
                    metadatas=[self._memory_to_metadata(memory)],
                )

                return memory

        return None

    def search_memories(
        self,
        user_id: str,
        query: str,
        memory_types: Optional[List[MemoryType]] = None,
        session_id: Optional[str] = None,
        min_importance: float = 0.0,
        tags: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> List[MemorySearchResult]:
        """
        Search memories semantically.

        Args:
            user_id: User identifier
            query: Search query
            memory_types: Types to search (default: all)
            session_id: Optional filter by session
            min_importance: Minimum importance score
            tags: Optional filter by tags
            top_k: Number of results per type

        Returns:
            List of search results
        """
        types_to_search = memory_types or [MemoryType.SESSION, MemoryType.LONGTERM]
        all_results = []

        for mtype in types_to_search:
            collection_name = self._get_collection_name(user_id, mtype)

            # Build where filter - ChromaDB requires $and for multiple conditions
            conditions = []
            if session_id and mtype == MemoryType.SESSION:
                conditions.append({"session_id": session_id})
            if min_importance > 0:
                conditions.append({"importance_score": {"$gte": min_importance}})

            # Wrap multiple conditions in $and, single condition as-is
            where = None
            if len(conditions) == 1:
                where = conditions[0]
            elif len(conditions) > 1:
                where = {"$and": conditions}

            results = self.vector_store.query(
                collection_name=collection_name,
                query_text=query,
                top_k=top_k,
                where=where,
            )

            for i, doc in enumerate(results["documents"]):
                metadata = results["metadatas"][i] if results["metadatas"] else {}
                distance = results["distances"][i] if results["distances"] else 0

                # Filter by tags if specified
                if tags:
                    mem_tags = metadata.get("tags", "").split(",")
                    if not any(t in mem_tags for t in tags):
                        continue

                memory = self._metadata_to_memory(doc, metadata)
                all_results.append(MemorySearchResult(
                    memory=memory,
                    relevance_score=1 - distance,
                ))

        # Sort by relevance
        all_results.sort(key=lambda x: x.relevance_score, reverse=True)
        return all_results[:top_k]

    def get_session_memories(
        self,
        user_id: str,
        session_id: str,
        limit: int = 50,
    ) -> List[MemoryEntry]:
        """
        Get all memories for a specific session.

        Args:
            user_id: User identifier
            session_id: Session identifier
            limit: Maximum results

        Returns:
            List of memories
        """
        collection_name = self._get_collection_name(user_id, MemoryType.SESSION)

        # Query with session filter
        # ChromaDB get() doesn't support where, so we query with empty string
        results = self.vector_store.query(
            collection_name=collection_name,
            query_text="",  # Will return all
            top_k=limit,
            where={"session_id": session_id},
        )

        memories = []
        for i, doc in enumerate(results["documents"]):
            metadata = results["metadatas"][i] if results["metadatas"] else {}
            memories.append(self._metadata_to_memory(doc, metadata))

        return memories

    def promote_to_longterm(
        self,
        user_id: str,
        memory_id: str,
    ) -> Optional[MemoryEntry]:
        """
        Promote a session memory to long-term storage.

        Args:
            user_id: User identifier
            memory_id: Memory to promote

        Returns:
            Promoted memory or None
        """
        # Get from session memory
        memory = self.get_memory(user_id, memory_id, MemoryType.SESSION)
        if not memory:
            return None

        # Delete from session
        session_collection = self._get_collection_name(user_id, MemoryType.SESSION)
        self.vector_store.delete_documents(session_collection, ids=[memory_id])

        # Add to longterm
        memory.memory_type = MemoryType.LONGTERM
        longterm_collection = self._get_collection_name(user_id, MemoryType.LONGTERM)

        self.vector_store.add_documents(
            collection_name=longterm_collection,
            texts=[memory.content],
            metadatas=[self._memory_to_metadata(memory)],
            ids=[memory_id],
        )

        return memory

    def update_importance(
        self,
        user_id: str,
        memory_id: str,
        importance_score: float,
        memory_type: Optional[MemoryType] = None,
    ) -> bool:
        """
        Update memory importance score.

        Args:
            user_id: User identifier
            memory_id: Memory identifier
            importance_score: New score (0.0 to 1.0)
            memory_type: Optional type hint

        Returns:
            True if updated
        """
        memory = self.get_memory(user_id, memory_id, memory_type)
        if not memory:
            return False

        memory.importance_score = importance_score
        collection_name = self._get_collection_name(user_id, memory.memory_type)

        return self.vector_store.update_documents(
            collection_name=collection_name,
            ids=[memory_id],
            metadatas=[self._memory_to_metadata(memory)],
        )

    def delete_memory(
        self,
        user_id: str,
        memory_id: str,
        memory_type: Optional[MemoryType] = None,
    ) -> bool:
        """
        Delete a specific memory.

        Args:
            user_id: User identifier
            memory_id: Memory identifier
            memory_type: Optional type hint

        Returns:
            True if deleted
        """
        types_to_check = [memory_type] if memory_type else list(MemoryType)

        for mtype in types_to_check:
            collection_name = self._get_collection_name(user_id, mtype)
            results = self.vector_store.get_by_ids(collection_name, [memory_id])

            if results["documents"]:
                return self.vector_store.delete_documents(
                    collection_name, ids=[memory_id]
                )

        return False

    def cleanup_session_memories(
        self,
        user_id: str,
        session_id: str,
        keep_important: bool = True,
        importance_threshold: float = 0.7,
    ) -> int:
        """
        Clean up session memories.

        Args:
            user_id: User identifier
            session_id: Session to clean
            keep_important: Keep memories above threshold
            importance_threshold: Importance threshold

        Returns:
            Number of memories deleted
        """
        memories = self.get_session_memories(user_id, session_id)
        deleted = 0

        for memory in memories:
            if keep_important and memory.importance_score >= importance_threshold:
                # Promote to long-term instead
                self.promote_to_longterm(user_id, memory.memory_id)
            else:
                if self.delete_memory(user_id, memory.memory_id, MemoryType.SESSION):
                    deleted += 1

        return deleted

    # ========================================================================
    # Decision Methods
    # ========================================================================

    def _decision_to_metadata(self, decision: AgentDecision) -> Dict[str, Any]:
        """Convert decision to metadata dict."""
        return {
            "decision_id": decision.decision_id,
            "user_id": decision.user_id or "",
            "session_id": decision.session_id or "",
            "decision_type": decision.decision_type,
            "confidence_score": decision.confidence_score,
            "created_at": decision.created_at.isoformat(),
            "related_resources": ",".join(decision.related_resources),
            "tags": ",".join(decision.tags),
        }

    def _metadata_to_decision(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> AgentDecision:
        """Convert metadata dict to AgentDecision."""
        # Parse content back into parts (stored as combined text)
        parts = content.split("\n---\n")
        context = parts[0] if len(parts) > 0 else ""
        reasoning = parts[1] if len(parts) > 1 else ""
        outcome = parts[2] if len(parts) > 2 else ""

        return AgentDecision(
            decision_id=metadata.get("decision_id", ""),
            user_id=metadata.get("user_id", ""),
            session_id=metadata.get("session_id", ""),
            decision_type=metadata.get("decision_type", ""),
            context=context,
            reasoning=reasoning,
            outcome=outcome,
            confidence_score=float(metadata.get("confidence_score", 0.5)),
            created_at=datetime.fromisoformat(metadata["created_at"]) if metadata.get("created_at") else datetime.utcnow(),
            related_resources=metadata.get("related_resources", "").split(",") if metadata.get("related_resources") else [],
            tags=metadata.get("tags", "").split(",") if metadata.get("tags") else [],
        )

    def store_decision(
        self,
        user_id: str,
        session_id: str,
        decision_type: str,
        context: str,
        reasoning: str,
        outcome: str,
        confidence_score: float = 0.5,
        related_resources: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> AgentDecision:
        """
        Store an agent decision for future reference.

        Args:
            user_id: User identifier
            session_id: Session identifier
            decision_type: Type of decision
            context: Context leading to decision
            reasoning: Reasoning process
            outcome: Decision outcome
            confidence_score: Confidence in decision
            related_resources: Related resource identifiers
            tags: Tags for categorization

        Returns:
            Created AgentDecision
        """
        decision_id = str(uuid.uuid4())
        now = datetime.utcnow()

        decision = AgentDecision(
            decision_id=decision_id,
            user_id=user_id,
            session_id=session_id,
            decision_type=decision_type,
            context=context,
            reasoning=reasoning,
            outcome=outcome,
            confidence_score=confidence_score,
            created_at=now,
            related_resources=related_resources or [],
            tags=tags or [],
        )

        # Combine text for semantic search
        combined_content = f"{context}\n---\n{reasoning}\n---\n{outcome}"

        collection_name = self.vector_store.build_collection_name(
            index_group="memory",
            subindex="decisions",
            user_id=user_id,
        )

        self.vector_store.add_documents(
            collection_name=collection_name,
            texts=[combined_content],
            metadatas=[self._decision_to_metadata(decision)],
            ids=[decision_id],
        )

        return decision

    def get_decision(
        self,
        user_id: str,
        decision_id: str,
    ) -> Optional[AgentDecision]:
        """
        Get a specific decision by ID.

        Args:
            user_id: User identifier
            decision_id: Decision identifier

        Returns:
            AgentDecision if found
        """
        collection_name = self.vector_store.build_collection_name(
            index_group="memory",
            subindex="decisions",
            user_id=user_id,
        )

        results = self.vector_store.get_by_ids(collection_name, [decision_id])

        if results["documents"]:
            return self._metadata_to_decision(
                results["documents"][0],
                results["metadatas"][0],
            )

        return None

    def search_decisions(
        self,
        user_id: str,
        query: str,
        decision_type: Optional[str] = None,
        session_id: Optional[str] = None,
        min_confidence: float = 0.0,
        top_k: int = 10,
    ) -> List[DecisionSearchResult]:
        """
        Search past agent decisions.

        Args:
            user_id: User identifier
            query: Search query
            decision_type: Optional filter by type
            session_id: Optional filter by session
            min_confidence: Minimum confidence score
            top_k: Number of results

        Returns:
            List of search results
        """
        collection_name = self.vector_store.build_collection_name(
            index_group="memory",
            subindex="decisions",
            user_id=user_id,
        )

        # Build filter conditions - ChromaDB requires $and for multiple conditions
        conditions = []
        if decision_type:
            conditions.append({"decision_type": decision_type})
        if session_id:
            conditions.append({"session_id": session_id})
        if min_confidence > 0:
            conditions.append({"confidence_score": {"$gte": min_confidence}})

        # Wrap multiple conditions in $and, single condition as-is
        where = None
        if len(conditions) == 1:
            where = conditions[0]
        elif len(conditions) > 1:
            where = {"$and": conditions}

        results = self.vector_store.query(
            collection_name=collection_name,
            query_text=query,
            top_k=top_k,
            where=where,
        )

        search_results = []
        for i, doc in enumerate(results["documents"]):
            metadata = results["metadatas"][i] if results["metadatas"] else {}
            distance = results["distances"][i] if results["distances"] else 0

            decision = self._metadata_to_decision(doc, metadata)
            search_results.append(DecisionSearchResult(
                decision=decision,
                relevance_score=1 - distance,
            ))

        return search_results

    def get_decisions_for_resource(
        self,
        user_id: str,
        resource_id: str,
        top_k: int = 20,
    ) -> List[AgentDecision]:
        """
        Get decisions related to a specific resource.

        Args:
            user_id: User identifier
            resource_id: Resource identifier
            top_k: Maximum results

        Returns:
            List of related decisions
        """
        # Search for the resource ID in related_resources
        results = self.search_decisions(
            user_id=user_id,
            query=resource_id,
            top_k=top_k,
        )

        # Filter to only those that actually reference this resource
        filtered = []
        for result in results:
            if resource_id in result.decision.related_resources:
                filtered.append(result.decision)

        return filtered
