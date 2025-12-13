from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.models.index_schemas import (
    SessionCreateRequest,
    SessionMessageRequest,
    SessionUpdateContextRequest,
    SessionUpdateStateRequest,
    SessionExtendRequest,
    SessionResponse,
    SessionListResponse,
    SessionData,
    SessionMessage,
    SessionSummary,
)
from app.services.session_service import SessionService
from app.api.deps import verify_api_key_or_token

router = APIRouter()

# Dependency to get session service
async def get_session_service() -> SessionService:
    return SessionService()


@router.post("/", response_model=SessionResponse)
async def create_session(
    request: SessionCreateRequest,
    auth: dict = Depends(verify_api_key_or_token),
    session_service: SessionService = Depends(get_session_service),
):
    """
    Create a new session.

    Sessions are stored in Redis with TTL-based expiration.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    session = await session_service.create_session(
        user_id=user_id,
        model_id=request.model_id,
        provider=request.provider,
        initial_context=request.initial_context,
        ttl_seconds=request.ttl_seconds,
    )

    return SessionResponse(session=session)


@router.get("/", response_model=SessionListResponse)
async def list_sessions(
    model_id: Optional[str] = Query(None, description="Filter by model ID"),
    active_only: bool = Query(True, description="Only show active sessions"),
    auth: dict = Depends(verify_api_key_or_token),
    session_service: SessionService = Depends(get_session_service),
):
    """
    List all sessions for the authenticated user.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    sessions = await session_service.list_sessions(
        user_id=user_id,
        model_id=model_id,
        active_only=active_only,
    )

    return SessionListResponse(sessions=sessions, total=len(sessions))


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    auth: dict = Depends(verify_api_key_or_token),
    session_service: SessionService = Depends(get_session_service),
):
    """
    Get session details by ID.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    session = await session_service.get_session(user_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(session=session)


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    auth: dict = Depends(verify_api_key_or_token),
    session_service: SessionService = Depends(get_session_service),
):
    """
    Delete a session.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    success = await session_service.delete_session(user_id, session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"message": "Session deleted", "session_id": session_id}


@router.post("/{session_id}/messages")
async def add_message(
    session_id: str,
    request: SessionMessageRequest,
    auth: dict = Depends(verify_api_key_or_token),
    session_service: SessionService = Depends(get_session_service),
):
    """
    Add a message to session history.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    message = SessionMessage(
        role=request.role,
        content=request.content,
        metadata=request.metadata,
    )

    success = await session_service.add_message(user_id, session_id, message)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"message": "Message added", "session_id": session_id}


@router.get("/{session_id}/messages")
async def get_messages(
    session_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    auth: dict = Depends(verify_api_key_or_token),
    session_service: SessionService = Depends(get_session_service),
):
    """
    Get messages from session history.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    messages = await session_service.get_messages(
        user_id=user_id,
        session_id=session_id,
        limit=limit,
        offset=offset,
    )

    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "messages": [m.model_dump() for m in messages],
        "total": len(messages),
        "session_id": session_id,
    }


@router.put("/{session_id}/context")
async def update_context(
    session_id: str,
    request: SessionUpdateContextRequest,
    auth: dict = Depends(verify_api_key_or_token),
    session_service: SessionService = Depends(get_session_service),
):
    """
    Update session context.

    Context can be merged with existing or replaced entirely.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    success = await session_service.update_context(
        user_id=user_id,
        session_id=session_id,
        context=request.context,
        merge=request.merge,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"message": "Context updated", "session_id": session_id}


@router.put("/{session_id}/state")
async def update_state(
    session_id: str,
    request: SessionUpdateStateRequest,
    auth: dict = Depends(verify_api_key_or_token),
    session_service: SessionService = Depends(get_session_service),
):
    """
    Update session state.

    State can be merged with existing or replaced entirely.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    success = await session_service.update_state(
        user_id=user_id,
        session_id=session_id,
        state=request.state,
        merge=request.merge,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"message": "State updated", "session_id": session_id}


@router.post("/{session_id}/extend")
async def extend_session(
    session_id: str,
    request: SessionExtendRequest,
    auth: dict = Depends(verify_api_key_or_token),
    session_service: SessionService = Depends(get_session_service),
):
    """
    Extend session TTL.
    """
    user_id = auth.get("user_id", auth.get("sub", "default_user"))

    success = await session_service.extend_ttl(
        user_id=user_id,
        session_id=session_id,
        additional_seconds=request.additional_seconds,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    return {
        "message": "Session extended",
        "session_id": session_id,
        "additional_seconds": request.additional_seconds,
    }
