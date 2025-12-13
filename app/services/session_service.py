import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

import redis.asyncio as aioredis

from app.config import get_settings
from app.models.index_schemas import (
    SessionData,
    SessionMessage,
    SessionSummary,
)


class SessionService:
    """
    Manages ephemeral session data in Redis.
    Supports per-model, per-user sessions with TTL.

    Key format: session:{user_id}:{session_id}
    """

    def __init__(self, redis_url: Optional[str] = None):
        settings = get_settings()
        self.redis_url = redis_url or settings.redis_url
        self.default_ttl = settings.session_default_ttl
        self._redis: Optional[aioredis.Redis] = None

    async def _get_redis(self) -> aioredis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    def _build_key(self, user_id: str, session_id: str) -> str:
        """Build Redis key for a session."""
        return f"session:{user_id}:{session_id}"

    def _build_user_pattern(self, user_id: str) -> str:
        """Build pattern to match all sessions for a user."""
        return f"session:{user_id}:*"

    async def create_session(
        self,
        user_id: str,
        model_id: str,
        provider: str,
        initial_context: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
    ) -> SessionData:
        """
        Create a new session.

        Args:
            user_id: User identifier
            model_id: LLM model identifier
            provider: LLM provider name
            initial_context: Optional initial context data
            ttl_seconds: Time-to-live in seconds

        Returns:
            Created SessionData
        """
        redis = await self._get_redis()
        session_id = str(uuid.uuid4())
        ttl = ttl_seconds or self.default_ttl
        now = datetime.utcnow()

        session = SessionData(
            session_id=session_id,
            user_id=user_id,
            model_id=model_id,
            provider=provider,
            created_at=now,
            last_activity=now,
            messages=[],
            context=initial_context or {},
            state={},
            ttl_seconds=ttl,
        )

        key = self._build_key(user_id, session_id)
        await redis.setex(
            key,
            ttl,
            session.model_dump_json(),
        )

        return session

    async def get_session(
        self,
        user_id: str,
        session_id: str,
    ) -> Optional[SessionData]:
        """
        Retrieve session data.

        Args:
            user_id: User identifier
            session_id: Session identifier

        Returns:
            SessionData if found, None otherwise
        """
        redis = await self._get_redis()
        key = self._build_key(user_id, session_id)
        data = await redis.get(key)

        if not data:
            return None

        return SessionData.model_validate_json(data)

    async def update_session(
        self,
        user_id: str,
        session_id: str,
        session: SessionData,
    ) -> bool:
        """
        Update session data.

        Args:
            user_id: User identifier
            session_id: Session identifier
            session: Updated session data

        Returns:
            True if successful
        """
        redis = await self._get_redis()
        key = self._build_key(user_id, session_id)

        # Get remaining TTL
        ttl = await redis.ttl(key)
        if ttl < 0:
            ttl = self.default_ttl

        session.last_activity = datetime.utcnow()

        await redis.setex(
            key,
            ttl,
            session.model_dump_json(),
        )
        return True

    async def add_message(
        self,
        user_id: str,
        session_id: str,
        message: SessionMessage,
    ) -> bool:
        """
        Add a message to session history.

        Args:
            user_id: User identifier
            session_id: Session identifier
            message: Message to add

        Returns:
            True if successful
        """
        session = await self.get_session(user_id, session_id)
        if not session:
            return False

        session.messages.append(message)
        return await self.update_session(user_id, session_id, session)

    async def get_messages(
        self,
        user_id: str,
        session_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[SessionMessage]:
        """
        Get recent messages from session.

        Args:
            user_id: User identifier
            session_id: Session identifier
            limit: Maximum messages to return
            offset: Number of messages to skip

        Returns:
            List of messages
        """
        session = await self.get_session(user_id, session_id)
        if not session:
            return []

        messages = session.messages
        if offset:
            messages = messages[offset:]
        if limit:
            messages = messages[:limit]

        return messages

    async def update_context(
        self,
        user_id: str,
        session_id: str,
        context: Dict[str, Any],
        merge: bool = True,
    ) -> bool:
        """
        Update session context.

        Args:
            user_id: User identifier
            session_id: Session identifier
            context: Context data to set/merge
            merge: If True, merge with existing; if False, replace

        Returns:
            True if successful
        """
        session = await self.get_session(user_id, session_id)
        if not session:
            return False

        if merge:
            session.context.update(context)
        else:
            session.context = context

        return await self.update_session(user_id, session_id, session)

    async def update_state(
        self,
        user_id: str,
        session_id: str,
        state: Dict[str, Any],
        merge: bool = True,
    ) -> bool:
        """
        Update session state.

        Args:
            user_id: User identifier
            session_id: Session identifier
            state: State data to set/merge
            merge: If True, merge with existing; if False, replace

        Returns:
            True if successful
        """
        session = await self.get_session(user_id, session_id)
        if not session:
            return False

        if merge:
            session.state.update(state)
        else:
            session.state = state

        return await self.update_session(user_id, session_id, session)

    async def delete_session(
        self,
        user_id: str,
        session_id: str,
    ) -> bool:
        """
        Delete a session.

        Args:
            user_id: User identifier
            session_id: Session identifier

        Returns:
            True if session was deleted
        """
        redis = await self._get_redis()
        key = self._build_key(user_id, session_id)
        result = await redis.delete(key)
        return result > 0

    async def list_sessions(
        self,
        user_id: str,
        model_id: Optional[str] = None,
        active_only: bool = True,
    ) -> List[SessionSummary]:
        """
        List all sessions for a user.

        Args:
            user_id: User identifier
            model_id: Optional filter by model
            active_only: Only include sessions with remaining TTL

        Returns:
            List of session summaries
        """
        redis = await self._get_redis()
        pattern = self._build_user_pattern(user_id)
        keys = []

        async for key in redis.scan_iter(match=pattern):
            keys.append(key)

        summaries = []
        for key in keys:
            data = await redis.get(key)
            if not data:
                continue

            session = SessionData.model_validate_json(data)

            # Filter by model if specified
            if model_id and session.model_id != model_id:
                continue

            # Get TTL
            ttl = await redis.ttl(key)
            if active_only and ttl < 0:
                continue

            summaries.append(SessionSummary(
                session_id=session.session_id,
                model_id=session.model_id,
                provider=session.provider,
                created_at=session.created_at,
                last_activity=session.last_activity,
                message_count=len(session.messages),
                ttl_remaining=ttl if ttl > 0 else None,
            ))

        # Sort by last activity, most recent first
        summaries.sort(key=lambda x: x.last_activity, reverse=True)
        return summaries

    async def extend_ttl(
        self,
        user_id: str,
        session_id: str,
        additional_seconds: int,
    ) -> bool:
        """
        Extend session TTL.

        Args:
            user_id: User identifier
            session_id: Session identifier
            additional_seconds: Seconds to add to TTL

        Returns:
            True if successful
        """
        redis = await self._get_redis()
        key = self._build_key(user_id, session_id)

        # Get current TTL
        current_ttl = await redis.ttl(key)
        if current_ttl < 0:
            return False

        new_ttl = current_ttl + additional_seconds
        await redis.expire(key, new_ttl)

        # Update session data with new TTL
        session = await self.get_session(user_id, session_id)
        if session:
            session.ttl_seconds = new_ttl
            await self.update_session(user_id, session_id, session)

        return True

    async def get_session_count(self, user_id: str) -> int:
        """
        Get total number of sessions for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of sessions
        """
        redis = await self._get_redis()
        pattern = self._build_user_pattern(user_id)
        count = 0

        async for _ in redis.scan_iter(match=pattern):
            count += 1

        return count

    async def clear_user_sessions(self, user_id: str) -> int:
        """
        Delete all sessions for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of sessions deleted
        """
        redis = await self._get_redis()
        pattern = self._build_user_pattern(user_id)
        keys = []

        async for key in redis.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            return await redis.delete(*keys)
        return 0
