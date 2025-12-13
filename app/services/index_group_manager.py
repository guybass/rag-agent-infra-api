"""
Index Group Manager - Cross-index query and management service.

Provides unified interface for querying across all index groups:
- Terraform (semantic + file system)
- Sessions (Redis)
- Memory (ChromaDB)
- Context (cloud state)
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.services.multi_vector_store import MultiVectorStoreService
from app.services.session_service import SessionService
from app.services.memory_service import MemoryService
from app.services.context_service import ContextService
from app.services.terraform.terraform_index_service import TerraformIndexService
from app.models.index_schemas import (
    IndexGroup,
    TerraformSearchResult,
    MemorySearchResult,
    DecisionSearchResult,
    ContextSearchResult,
    UnifiedSearchResult,
    IndexGroupStats,
    MemoryType,
    ContextSourceType,
)
from app.config import get_settings


class IndexGroupManager:
    """
    Manages cross-index queries and provides unified search functionality.

    Aggregates results from:
    - Terraform index (ChromaDB + filesystem)
    - Session index (Redis)
    - Memory index (ChromaDB)
    - Context index (ChromaDB)
    """

    def __init__(
        self,
        vector_store: Optional[MultiVectorStoreService] = None,
        session_service: Optional[SessionService] = None,
        memory_service: Optional[MemoryService] = None,
        context_service: Optional[ContextService] = None,
        terraform_service: Optional[TerraformIndexService] = None,
    ):
        self.vector_store = vector_store or MultiVectorStoreService()
        self.session_service = session_service or SessionService()
        self.memory_service = memory_service or MemoryService(self.vector_store)
        self.context_service = context_service or ContextService(self.vector_store)
        self.terraform_service = terraform_service or TerraformIndexService(self.vector_store)

    async def unified_search(
        self,
        user_id: str,
        query: str,
        index_groups: List[IndexGroup],
        session_id: Optional[str] = None,
        account_id: Optional[str] = None,
        top_k_per_group: int = 5,
    ) -> UnifiedSearchResult:
        """
        Search across multiple index groups.

        Args:
            user_id: User identifier
            query: Search query
            index_groups: Index groups to search
            session_id: Optional session ID for session-specific results
            account_id: Optional account ID for terraform/context filtering
            top_k_per_group: Number of results per group

        Returns:
            UnifiedSearchResult with results from each group
        """
        result = UnifiedSearchResult()

        # Search Terraform
        if IndexGroup.TERRAFORM in index_groups:
            terraform_results = self._search_terraform(
                user_id=user_id,
                query=query,
                account_id=account_id,
                top_k=top_k_per_group,
            )
            result.terraform = terraform_results

        # Search Memory
        if IndexGroup.MEMORY in index_groups:
            memory_results = self._search_memory(
                user_id=user_id,
                query=query,
                session_id=session_id,
                top_k=top_k_per_group,
            )
            result.memory = memory_results

            # Also search decisions
            decision_results = self._search_decisions(
                user_id=user_id,
                query=query,
                session_id=session_id,
                top_k=top_k_per_group,
            )
            result.decisions = decision_results

        # Search Context
        if IndexGroup.CONTEXT in index_groups:
            context_results = self._search_context(
                user_id=user_id,
                query=query,
                account_id=account_id,
                top_k=top_k_per_group,
            )
            result.context = context_results

        return result

    def _search_terraform(
        self,
        user_id: str,
        query: str,
        account_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[TerraformSearchResult]:
        """Search terraform index."""
        results = self.terraform_service.semantic_search(
            user_id=user_id,
            query=query,
            account_id=account_id,
            top_k=top_k,
        )
        return results

    def _search_memory(
        self,
        user_id: str,
        query: str,
        session_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[MemorySearchResult]:
        """Search memory index."""
        results = self.memory_service.search_memories(
            user_id=user_id,
            query=query,
            memory_types=[MemoryType.SESSION, MemoryType.LONGTERM],
            session_id=session_id,
            top_k=top_k,
        )
        return results

    def _search_decisions(
        self,
        user_id: str,
        query: str,
        session_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[DecisionSearchResult]:
        """Search decisions index."""
        results = self.memory_service.search_decisions(
            user_id=user_id,
            query=query,
            session_id=session_id,
            top_k=top_k,
        )
        return results

    def _search_context(
        self,
        user_id: str,
        query: str,
        account_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[ContextSearchResult]:
        """Search context index."""
        results = self.context_service.search_context(
            user_id=user_id,
            query=query,
            account_id=account_id,
            top_k=top_k,
        )
        return results

    async def build_agent_context(
        self,
        user_id: str,
        session_id: str,
        query: str,
        include_groups: List[IndexGroup],
        max_context_tokens: int = 4000,
        account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build comprehensive context for an agent.

        Retrieves relevant information from all specified index groups
        and formats it for agent consumption.

        Args:
            user_id: User identifier
            session_id: Session ID
            query: Current query/task
            include_groups: Index groups to include
            max_context_tokens: Maximum context size (approximate)
            account_id: Optional account ID filter

        Returns:
            Dict with context string and source counts
        """
        # Estimate chars per group based on token budget
        # Rough estimate: 4 chars per token
        char_budget = max_context_tokens * 4
        chars_per_group = char_budget // len(include_groups) if include_groups else 0

        context_parts = []
        sources = {}

        # Get session context if available
        if IndexGroup.SESSIONS in include_groups:
            session_context = await self._get_session_context(
                user_id=user_id,
                session_id=session_id,
                max_chars=chars_per_group,
            )
            if session_context:
                context_parts.append(f"## Session Context\n{session_context}")
                sources["sessions"] = 1

        # Get memory context
        if IndexGroup.MEMORY in include_groups:
            memory_context = self._get_memory_context(
                user_id=user_id,
                query=query,
                session_id=session_id,
                max_chars=chars_per_group,
            )
            if memory_context:
                context_parts.append(f"## Relevant Memories\n{memory_context['text']}")
                sources["memories"] = memory_context["count"]

            # Get decision context
            decision_context = self._get_decision_context(
                user_id=user_id,
                query=query,
                session_id=session_id,
                max_chars=chars_per_group // 2,
            )
            if decision_context:
                context_parts.append(f"## Past Decisions\n{decision_context['text']}")
                sources["decisions"] = decision_context["count"]

        # Get terraform context
        if IndexGroup.TERRAFORM in include_groups:
            terraform_context = self._get_terraform_context(
                user_id=user_id,
                query=query,
                account_id=account_id,
                max_chars=chars_per_group,
            )
            if terraform_context:
                context_parts.append(f"## Terraform Context\n{terraform_context['text']}")
                sources["terraform"] = terraform_context["count"]

        # Get cloud context
        if IndexGroup.CONTEXT in include_groups:
            cloud_context = self._get_cloud_context(
                user_id=user_id,
                query=query,
                account_id=account_id,
                max_chars=chars_per_group,
            )
            if cloud_context:
                context_parts.append(f"## Cloud Context\n{cloud_context['text']}")
                sources["context"] = cloud_context["count"]

        context_string = "\n\n".join(context_parts)

        return {
            "context": context_string,
            "sources": sources,
            "session_id": session_id,
        }

    async def _get_session_context(
        self,
        user_id: str,
        session_id: str,
        max_chars: int,
    ) -> Optional[str]:
        """Get recent session context."""
        try:
            session = await self.session_service.get_session(user_id, session_id)
            if not session:
                return None

            # Format recent messages
            messages = session.messages[-10:]  # Last 10 messages
            formatted = []
            for msg in messages:
                formatted.append(f"[{msg.role}]: {msg.content[:200]}...")

            context = "\n".join(formatted)
            return context[:max_chars]
        except Exception:
            return None

    def _get_memory_context(
        self,
        user_id: str,
        query: str,
        session_id: Optional[str],
        max_chars: int,
    ) -> Optional[Dict[str, Any]]:
        """Get relevant memory context."""
        results = self.memory_service.search_memories(
            user_id=user_id,
            query=query,
            memory_types=[MemoryType.SESSION, MemoryType.LONGTERM],
            session_id=session_id,
            top_k=5,
        )

        if not results:
            return None

        formatted = []
        for r in results:
            formatted.append(f"- {r.memory.content[:300]}... (relevance: {r.relevance_score:.2f})")

        text = "\n".join(formatted)
        return {
            "text": text[:max_chars],
            "count": len(results),
        }

    def _get_decision_context(
        self,
        user_id: str,
        query: str,
        session_id: Optional[str],
        max_chars: int,
    ) -> Optional[Dict[str, Any]]:
        """Get relevant decision context."""
        results = self.memory_service.search_decisions(
            user_id=user_id,
            query=query,
            session_id=session_id,
            top_k=3,
        )

        if not results:
            return None

        formatted = []
        for r in results:
            formatted.append(
                f"- Decision: {r.decision.decision_type}\n"
                f"  Reasoning: {r.decision.reasoning[:200]}...\n"
                f"  Outcome: {r.decision.outcome[:100]}..."
            )

        text = "\n".join(formatted)
        return {
            "text": text[:max_chars],
            "count": len(results),
        }

    def _get_terraform_context(
        self,
        user_id: str,
        query: str,
        account_id: Optional[str],
        max_chars: int,
    ) -> Optional[Dict[str, Any]]:
        """Get relevant terraform context."""
        results = self.terraform_service.semantic_search(
            user_id=user_id,
            query=query,
            account_id=account_id,
            top_k=5,
        )

        if not results:
            return None

        formatted = []
        for r in results:
            formatted.append(
                f"- File: {r.metadata.file_path}\n"
                f"  Category: {r.metadata.category}\n"
                f"  Content: {r.content[:200]}..."
            )

        text = "\n".join(formatted)
        return {
            "text": text[:max_chars],
            "count": len(results),
        }

    def _get_cloud_context(
        self,
        user_id: str,
        query: str,
        account_id: Optional[str],
        max_chars: int,
    ) -> Optional[Dict[str, Any]]:
        """Get relevant cloud context."""
        results = self.context_service.search_context(
            user_id=user_id,
            query=query,
            account_id=account_id,
            top_k=5,
        )

        if not results:
            return None

        formatted = []
        for r in results:
            formatted.append(
                f"- Resource: {r.context.resource.resource_type}/{r.context.resource.resource_id}\n"
                f"  Region: {r.context.resource.region}\n"
                f"  Source: {r.context.source_type.value}"
            )

        text = "\n".join(formatted)
        return {
            "text": text[:max_chars],
            "count": len(results),
        }

    def get_all_stats(self, user_id: str) -> List[IndexGroupStats]:
        """
        Get statistics for all index groups.

        Args:
            user_id: User identifier

        Returns:
            List of IndexGroupStats for each group
        """
        stats = []

        # Terraform stats
        terraform_stats = self._get_terraform_stats(user_id)
        stats.append(IndexGroupStats(
            index_group="terraform",
            collections=terraform_stats.get("collections", 0),
            total_documents=terraform_stats.get("documents", 0),
            details=terraform_stats,
        ))

        # Memory stats
        memory_stats = self._get_memory_stats(user_id)
        stats.append(IndexGroupStats(
            index_group="memory",
            collections=memory_stats.get("collections", 0),
            total_documents=memory_stats.get("documents", 0),
            details=memory_stats,
        ))

        # Context stats
        context_stats = self._get_context_stats(user_id)
        stats.append(IndexGroupStats(
            index_group="context",
            collections=context_stats.get("collections", 0),
            total_documents=context_stats.get("documents", 0),
            details=context_stats,
        ))

        # Session stats (from Redis)
        session_stats = self._get_session_stats(user_id)
        stats.append(IndexGroupStats(
            index_group="sessions",
            collections=1,  # Single Redis namespace
            total_documents=session_stats.get("session_count", 0),
            details=session_stats,
        ))

        return stats

    def _get_terraform_stats(self, user_id: str) -> Dict[str, Any]:
        """Get terraform index statistics."""
        pattern = f"^terraform__.*__{user_id}"
        collections = self.vector_store.list_collections(pattern=pattern)

        total_docs = 0
        for coll in collections:
            try:
                count = self.vector_store.get_collection_count(coll)
                total_docs += count
            except Exception:
                pass

        return {
            "collections": len(collections),
            "documents": total_docs,
            "collection_names": collections[:10],  # First 10
        }

    def _get_memory_stats(self, user_id: str) -> Dict[str, Any]:
        """Get memory index statistics."""
        pattern = f"^memory__.*__{user_id}"
        collections = self.vector_store.list_collections(pattern=pattern)

        total_docs = 0
        session_count = 0
        longterm_count = 0
        decision_count = 0

        for coll in collections:
            try:
                count = self.vector_store.get_collection_count(coll)
                total_docs += count
                if "session" in coll:
                    session_count += count
                elif "longterm" in coll:
                    longterm_count += count
                elif "decision" in coll:
                    decision_count += count
            except Exception:
                pass

        return {
            "collections": len(collections),
            "documents": total_docs,
            "session_memories": session_count,
            "longterm_memories": longterm_count,
            "decisions": decision_count,
        }

    def _get_context_stats(self, user_id: str) -> Dict[str, Any]:
        """Get context index statistics."""
        pattern = f"^context__.*__{user_id}"
        collections = self.vector_store.list_collections(pattern=pattern)

        total_docs = 0
        state_count = 0
        live_count = 0
        general_count = 0

        for coll in collections:
            try:
                count = self.vector_store.get_collection_count(coll)
                total_docs += count
                if "state" in coll:
                    state_count += count
                elif "live" in coll:
                    live_count += count
                elif "general" in coll:
                    general_count += count
            except Exception:
                pass

        return {
            "collections": len(collections),
            "documents": total_docs,
            "state_resources": state_count,
            "live_resources": live_count,
            "general_contexts": general_count,
        }

    def _get_session_stats(self, user_id: str) -> Dict[str, Any]:
        """Get session statistics from Redis."""
        try:
            # Note: This is synchronous, would need async version in production
            sessions = self.session_service._list_sessions_sync(user_id)
            return {
                "session_count": len(sessions),
                "active_sessions": len([s for s in sessions if s.get("ttl_remaining", 0) > 0]),
            }
        except Exception:
            return {
                "session_count": 0,
                "active_sessions": 0,
            }

    def cleanup_user_data(self, user_id: str) -> Dict[str, int]:
        """
        Clean up all data for a user across all index groups.

        Args:
            user_id: User identifier

        Returns:
            Dict with counts of deleted items per group
        """
        deleted = {
            "terraform": 0,
            "memory": 0,
            "context": 0,
            "sessions": 0,
        }

        # Delete terraform collections
        tf_pattern = f"^terraform__.*__{user_id}"
        tf_collections = self.vector_store.list_collections(pattern=tf_pattern)
        for coll in tf_collections:
            try:
                self.vector_store.delete_collection(coll)
                deleted["terraform"] += 1
            except Exception:
                pass

        # Delete memory collections
        mem_pattern = f"^memory__.*__{user_id}"
        mem_collections = self.vector_store.list_collections(pattern=mem_pattern)
        for coll in mem_collections:
            try:
                self.vector_store.delete_collection(coll)
                deleted["memory"] += 1
            except Exception:
                pass

        # Delete context collections
        ctx_pattern = f"^context__.*__{user_id}"
        ctx_collections = self.vector_store.list_collections(pattern=ctx_pattern)
        for coll in ctx_collections:
            try:
                self.vector_store.delete_collection(coll)
                deleted["context"] += 1
            except Exception:
                pass

        # Sessions would need async cleanup
        # For now, leave sessions to expire naturally via TTL

        return deleted
