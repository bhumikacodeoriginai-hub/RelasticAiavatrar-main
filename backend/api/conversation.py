"""
Conversation API endpoints.
Handles real-time conversation between visitors and AI avatar.
"""

import uuid
import base64
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from database.database import get_db
from database.visitors import VisitorRepository
from ai.bedrock import BedrockClient
from ai.conversation_manager import ConversationManager, ConversationState
from ai.prompts import VisitorContext, VisitorStatus
from voice.text_to_speech import TextToSpeech
from vision.face_matching import FaceMatchResult, MatchResult

logger = structlog.get_logger()

router = APIRouter(prefix="/api/conversation", tags=["conversation"])


# === Pydantic Schemas ===

class StartConversationRequest(BaseModel):
    """Request to start a new conversation."""
    match_status: str = Field(..., description="'match_found' or 'no_match'")
    person_id: Optional[str] = None
    person_name: Optional[str] = None
    visit_count: int = 0
    company: Optional[str] = None
    face_embedding: Optional[List[float]] = None


class MessageRequest(BaseModel):
    """Request with user's transcribed speech."""
    session_id: str
    text: str = Field(..., min_length=1)


class ConversationResponse(BaseModel):
    """Response from the AI avatar."""
    session_id: str
    text: str
    audio_base64: Optional[str] = None
    speech_marks: Optional[list] = None
    state: str
    visitor_name: Optional[str] = None


class SessionInfo(BaseModel):
    """Information about an active session."""
    session_id: str
    state: str
    visitor_name: Optional[str] = None
    message_count: int
    started_at: str


# === Dependency to get shared services ===

def get_conversation_manager(request: Request) -> ConversationManager:
    """Get the conversation manager from app state."""
    return request.app.state.conversation_manager


def get_tts(request: Request) -> TextToSpeech:
    """Get the TTS service from app state."""
    return request.app.state.tts


# === Endpoints ===

@router.post("/start", response_model=ConversationResponse)
async def start_conversation(
    req: StartConversationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Start a new conversation session.
    Called when the vision pipeline detects and identifies (or fails to identify) a person.
    """
    conv_manager = get_conversation_manager(request)
    tts = get_tts(request)

    # Build face match result
    if req.match_status == "match_found" and req.person_id:
        repo = VisitorRepository(db)
        person = await repo.get_person_by_id(uuid.UUID(req.person_id))
        match_result = FaceMatchResult(
            status=MatchResult.MATCH_FOUND,
            person=person,
            confidence=0.9
        )
    else:
        match_result = FaceMatchResult(
            status=MatchResult.NO_MATCH,
            message="New visitor"
        )

    # Start conversation session
    session = await conv_manager.start_session(match_result)

    # Generate initial greeting
    greeting_text = await conv_manager.generate_greeting(session)

    # Generate audio for greeting
    audio_base64 = None
    speech_marks = None
    if greeting_text:
        audio_bytes = await tts.synthesize(greeting_text)
        if audio_bytes:
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

        # Get speech marks for lip sync
        speech_marks = await tts.get_speech_marks(greeting_text)

    logger.info(
        "Conversation started",
        session_id=session.session_id,
        state=session.state.value
    )

    return ConversationResponse(
        session_id=session.session_id,
        text=greeting_text,
        audio_base64=audio_base64,
        speech_marks=speech_marks,
        state=session.state.value,
        visitor_name=session.visitor_context.name
    )


@router.post("/message", response_model=ConversationResponse)
async def send_message(
    req: MessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Send a user message (transcribed speech) and get AI response.
    This is the main conversation loop endpoint.
    """
    conv_manager = get_conversation_manager(request)
    tts = get_tts(request)

    # Process user input through conversation manager
    response_text = await conv_manager.process_user_input(
        session_id=req.session_id,
        user_text=req.text
    )

    # Get session state
    session = conv_manager.get_session(req.session_id)
    state = session.state.value if session else "ended"

    # Generate audio
    audio_base64 = None
    speech_marks = None
    if response_text:
        audio_bytes = await tts.synthesize(response_text)
        if audio_bytes:
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

        speech_marks = await tts.get_speech_marks(response_text)

    # Check if consent was granted (need to register face)
    visitor_name = None
    if session:
        visitor_name = session.visitor_context.name

        # Check for consent signal in messages
        if session.messages:
            last_system_msg = next(
                (m for m in reversed(session.messages) if m.get("role") == "system"),
                None
            )
            if last_system_msg and last_system_msg.get("content") == "CONSENT_GRANTED":
                # Trigger registration (handled by frontend/websocket)
                pass

    return ConversationResponse(
        session_id=req.session_id,
        text=response_text,
        audio_base64=audio_base64,
        speech_marks=speech_marks,
        state=state,
        visitor_name=visitor_name
    )


@router.post("/end/{session_id}")
async def end_conversation(
    session_id: str,
    request: Request
):
    """End an active conversation session."""
    conv_manager = get_conversation_manager(request)
    summary = await conv_manager.end_session(session_id)

    if not summary:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"message": "Conversation ended", "summary": summary}


@router.get("/session/{session_id}", response_model=SessionInfo)
async def get_session_info(
    session_id: str,
    request: Request
):
    """Get information about an active conversation session."""
    conv_manager = get_conversation_manager(request)
    session = conv_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionInfo(
        session_id=session.session_id,
        state=session.state.value,
        visitor_name=session.visitor_context.name,
        message_count=len(session.messages),
        started_at=session.started_at.isoformat()
    )


@router.get("/active")
async def get_active_sessions(request: Request):
    """Get count of active conversation sessions."""
    conv_manager = get_conversation_manager(request)
    return {
        "active_sessions": conv_manager.get_active_session_count()
    }
