"""
WebSocket endpoints for real-time communication.
Handles:
- Real-time camera frame processing
- Live conversation (speech-to-text → AI → text-to-speech)
- Avatar animation control
- Status updates to dashboard
"""

import json
import asyncio
import base64
import uuid
import time
import traceback
from typing import Dict, Set, Optional

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import structlog

from ai.conversation_manager import ConversationManager, ConversationState
from voice.text_to_speech import TextToSpeech
from vision.face_matching import FaceMatchResult, MatchResult

logger = structlog.get_logger()

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages all active WebSocket connections."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.dashboard_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info("WebSocket connected", client_id=client_id)

    async def connect_dashboard(self, websocket: WebSocket) -> None:
        """Accept a new dashboard WebSocket connection."""
        await websocket.accept()
        self.dashboard_connections.add(websocket)
        logger.info("Dashboard WebSocket connected")

    def disconnect(self, client_id: str) -> None:
        """Remove a WebSocket connection."""
        self.active_connections.pop(client_id, None)
        logger.info("WebSocket disconnected", client_id=client_id)

    def disconnect_dashboard(self, websocket: WebSocket) -> None:
        """Remove a dashboard connection."""
        self.dashboard_connections.discard(websocket)

    async def send_to_client(self, client_id: str, message: dict) -> None:
        """Send a message to a specific client."""
        ws = self.active_connections.get(client_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error("Error sending to client", error=str(e))
                self.disconnect(client_id)

    async def broadcast_to_dashboards(self, message: dict) -> None:
        """Broadcast a message to all dashboard connections."""
        disconnected = set()
        for ws in self.dashboard_connections:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.add(ws)

        for ws in disconnected:
            self.dashboard_connections.discard(ws)


# Global connection manager
ws_manager = ConnectionManager()


@router.websocket("/ws/conversation/{client_id}")
async def conversation_websocket(websocket: WebSocket, client_id: str):
    """
    Main WebSocket for real-time conversation.

    Protocol:
    Client sends:
        {"type": "speech", "text": "...", "is_final": true/false}
        {"type": "frame", "data": "<base64 image>"}
        {"type": "start_session", "match_status": "...", "person_id": "..."}
        {"type": "end_session", "session_id": "..."}
        {"type": "ping"}

    Server sends:
        {"type": "response", "text": "...", "audio": "<base64>", "speech_marks": [...]}
        {"type": "detection", "person_detected": true, "face_detected": true, ...}
        {"type": "state", "state": "...", "session_id": "..."}
        {"type": "error", "message": "..."}
        {"type": "pong"}
    """
    await ws_manager.connect(websocket, client_id)

    # Get services from app state
    app = websocket.app
    conv_manager: ConversationManager = app.state.conversation_manager
    tts: TextToSpeech = app.state.tts
    current_session_id: Optional[str] = None

    try:
        while True:
            # Receive message from client
            try:
                raw_data = await websocket.receive_text()
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                await ws_manager.send_to_client(client_id, {
                    "type": "error",
                    "message": "Invalid JSON"
                })
                continue

            msg_type = data.get("type", "")

            try:
                if msg_type == "ping":
                    await ws_manager.send_to_client(client_id, {"type": "pong"})

                elif msg_type == "speech":
                    await handle_speech(
                        client_id, data, conv_manager, tts, current_session_id
                    )

                elif msg_type == "start_session":
                    current_session_id = await handle_start_session(
                        client_id, data, conv_manager, tts
                    )

                elif msg_type == "end_session":
                    if current_session_id:
                        await handle_end_session(client_id, conv_manager, current_session_id)
                        current_session_id = None

                elif msg_type == "frame":
                    # Camera frame - just acknowledge for now
                    pass

                else:
                    await ws_manager.send_to_client(client_id, {
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}"
                    })

            except Exception as e:
                error_msg = str(e)
                logger.error(
                    "Error handling WebSocket message",
                    error=error_msg,
                    msg_type=msg_type,
                    traceback=traceback.format_exc()
                )
                await ws_manager.send_to_client(client_id, {
                    "type": "error",
                    "message": f"Server error: {error_msg}"
                })

    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
        if current_session_id:
            await conv_manager.end_session(current_session_id)
        logger.info("Client disconnected", client_id=client_id)
    except Exception as e:
        logger.error("WebSocket fatal error", error=str(e), client_id=client_id)
        ws_manager.disconnect(client_id)


async def handle_speech(
    client_id: str,
    data: dict,
    conv_manager: ConversationManager,
    tts: TextToSpeech,
    session_id: Optional[str]
) -> None:
    """Handle user speech input."""
    text = data.get("text", "")
    is_final = data.get("is_final", True)

    if not is_final or not text.strip():
        return

    if not session_id:
        await ws_manager.send_to_client(client_id, {
            "type": "error",
            "message": "No active session."
        })
        return

    logger.info("Processing speech", text=text[:50], session_id=session_id)

    # Process through conversation manager
    try:
        response_text = await conv_manager.process_user_input(
            session_id=session_id,
            user_text=text
        )
    except Exception as e:
        logger.error("Bedrock/AI error", error=str(e))
        response_text = f"I heard you say: '{text}'. I'm having trouble connecting right now, but I'm here to help!"

    # Save conversation to MySQL (non-blocking, skip if DB unavailable)
    try:
        from database.database import AsyncSessionLocal
        if AsyncSessionLocal:
            from database.mysql_visitor import MySQLVisitorService
            async with AsyncSessionLocal() as db:
                svc = MySQLVisitorService(db)
                session = conv_manager.get_session(session_id)
                
                if session and session.visitor_context.name:
                    visitor = await svc.find_visitor_by_name(session.visitor_context.name)
                    
                    if not visitor:
                        vid = await svc.register_visitor(name=session.visitor_context.name)
                        await svc.log_visit(vid)
                        logger.info("NEW visitor saved", name=session.visitor_context.name, id=vid)
                        
                        # Tell frontend to register face for this visitor
                        await ws_manager.send_to_client(client_id, {
                            "type": "register_face",
                            "name": session.visitor_context.name
                        })
                    elif visitor:
                        await svc.save_conversation(visitor['id'], 'visitor', text)
                        await svc.save_conversation(visitor['id'], 'ai', response_text)
    except Exception as e:
        logger.warning("DB save skipped", error=str(e))

    # Generate audio (non-critical)
    audio_base64 = None
    try:
        if response_text and tts._initialized:
            audio_bytes = await tts.synthesize(response_text)
            if audio_bytes:
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
    except Exception as e:
        logger.warning("TTS failed", error=str(e))

    # Get current state
    session = conv_manager.get_session(session_id)
    state = session.state.value if session else "ended"

    # Send response
    await ws_manager.send_to_client(client_id, {
        "type": "response",
        "text": response_text,
        "audio": audio_base64,
        "state": state,
        "session_id": session_id,
        "visitor_name": session.visitor_context.name if session else None
    })


async def handle_start_session(
    client_id: str,
    data: dict,
    conv_manager: ConversationManager,
    tts: TextToSpeech
) -> str:
    """Handle start of a new conversation session. Returns session_id."""
    match_status = data.get("match_status", "no_match")
    person_name = data.get("person_name")
    visit_count = data.get("visit_count", 0)

    logger.info("Starting session", match_status=match_status, person_name=person_name)

    # Build match result
    if match_status == "match_found" and person_name:
        person = type('Person', (), {
            'person_id': str(uuid.uuid4()),
            'name': person_name or "Visitor",
            'company': data.get("company"),
            'role': data.get("role"),
            'visit_count': visit_count,
            'last_seen': None
        })()
        match_result = FaceMatchResult(
            status=MatchResult.MATCH_FOUND,
            person=person,
            confidence=0.9
        )
    else:
        match_result = FaceMatchResult(
            status=MatchResult.NO_MATCH
        )

    # Start session
    session = await conv_manager.start_session(match_result)

    # Generate greeting
    try:
        if match_status == "match_found" and person_name:
            # RETURNING VISITOR - increment visit count ONCE
            try:
                from database.database import AsyncSessionLocal
                if AsyncSessionLocal:
                    from sqlalchemy import text as sql_text
                    async with AsyncSessionLocal() as db:
                        await db.execute(
                            sql_text("UPDATE visitor SET last_seen=NOW(), visit_count=visit_count+1 WHERE LOWER(name)=LOWER(:name)"),
                            {"name": person_name}
                        )
                        await db.commit()
                        logger.info("Updated last_seen for returning visitor", name=person_name)
            except Exception as e:
                logger.warning("DB update failed", error=str(e))
            
            # Direct greeting with name
            greeting = f"Hi {person_name}! Welcome back to Code Origin.AI. How can I help you today?"
            from ai.conversation_manager import ConversationState
            session.state = ConversationState.ACTIVE_CONVERSATION
            session.visitor_context.name = person_name
            session.add_message("assistant", greeting)
        else:
            # NEW VISITOR - ask Bedrock or use fallback
            greeting = await conv_manager.generate_greeting(session)
    except Exception as e:
        logger.error("Greeting generation failed", error=str(e))
        if match_status == "match_found" and person_name:
            greeting = f"Hi {person_name}! Welcome back to Code Origin.AI. How can I help you today?"
        else:
            greeting = "Hello! Welcome to Code Origin.AI. I don't think we've met before. May I know your name?"

    # Generate audio (non-critical)
    audio_base64 = None
    speech_marks = None
    try:
        if greeting and tts._initialized:
            audio_bytes = await tts.synthesize(greeting)
            if audio_bytes:
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            speech_marks = await tts.get_speech_marks(greeting)
    except Exception as e:
        logger.warning("TTS failed for greeting", error=str(e))

    await ws_manager.send_to_client(client_id, {
        "type": "response",
        "text": greeting,
        "audio": audio_base64,
        "speech_marks": speech_marks,
        "state": session.state.value,
        "session_id": session.session_id
    })

    # Broadcast to dashboard
    await ws_manager.broadcast_to_dashboards({
        "type": "new_session",
        "session_id": session.session_id,
        "visitor_name": session.visitor_context.name,
        "match_status": match_status
    })

    return session.session_id


async def handle_end_session(
    client_id: str,
    conv_manager: ConversationManager,
    session_id: str
) -> None:
    """Handle end of a conversation session."""
    summary = await conv_manager.end_session(session_id)

    await ws_manager.send_to_client(client_id, {
        "type": "state",
        "state": "ended",
        "session_id": session_id,
        "summary": summary
    })

    await ws_manager.broadcast_to_dashboards({
        "type": "session_ended",
        "session_id": session_id,
        "summary": summary
    })


@router.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """WebSocket for the management dashboard real-time updates."""
    await ws_manager.connect_dashboard(websocket)

    try:
        while True:
            try:
                raw_data = await websocket.receive_text()
                data = json.loads(raw_data)
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                continue
    except WebSocketDisconnect:
        ws_manager.disconnect_dashboard(websocket)
    except Exception as e:
        logger.error("Dashboard WebSocket error", error=str(e))
        ws_manager.disconnect_dashboard(websocket)
