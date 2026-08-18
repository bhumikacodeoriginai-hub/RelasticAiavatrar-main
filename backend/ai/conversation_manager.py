"""
Conversation Manager.
Orchestrates the full conversation flow between visitor and AI avatar.
Manages state machine transitions and integrates all AI components.
"""

import uuid
import asyncio
from typing import Optional, Dict, List, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import structlog

from ai.bedrock import BedrockClient
from ai.prompts import PromptBuilder, VisitorContext, VisitorStatus
from database.models import Person
from vision.face_matching import FaceMatchResult, MatchResult

logger = structlog.get_logger()


class ConversationState(str, Enum):
    """State machine for conversation flow."""
    IDLE = "idle"
    GREETING_NEW = "greeting_new"
    GREETING_RETURNING = "greeting_returning"
    WAITING_FOR_NAME = "waiting_for_name"
    ASKING_CONSENT = "asking_consent"
    ACTIVE_CONVERSATION = "active_conversation"
    FAREWELL = "farewell"
    ENDED = "ended"


@dataclass
class ConversationSession:
    """Represents an active conversation session."""
    session_id: str
    state: ConversationState = ConversationState.IDLE
    visitor_context: VisitorContext = field(default_factory=VisitorContext)
    messages: List[Dict[str, str]] = field(default_factory=list)
    person_id: Optional[uuid.UUID] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.visitor_context.conversation_history = self.messages
        self.last_activity = datetime.utcnow()


class ConversationManager:
    """
    Manages conversation sessions and orchestrates the AI interaction flow.

    State Machine:
    1. Person detected → Identify (known/new)
    2. Known person → Generate personalized greeting
    3. New person → Welcome + ask name
    4. Name received → Ask consent for face storage
    5. Consent given → Register + continue conversation
    6. Active conversation → Llama handles responses
    7. Person leaves → End session
    """

    def __init__(self, bedrock_client: BedrockClient):
        """
        Initialize the conversation manager.

        Args:
            bedrock_client: AWS Bedrock client for Llama
        """
        self.bedrock = bedrock_client
        self.active_sessions: Dict[str, ConversationSession] = {}
        self._on_response_callback: Optional[Callable] = None
        self.prompt_builder = PromptBuilder()

    def on_response(self, callback: Callable[[str, str], Awaitable[None]]) -> None:
        """Register callback for when AI generates a response."""
        self._on_response_callback = callback

    async def start_session(
        self,
        match_result: FaceMatchResult
    ) -> ConversationSession:
        """
        Start a new conversation session based on face match result.

        Args:
            match_result: Result from face recognition

        Returns:
            New ConversationSession
        """
        session_id = str(uuid.uuid4())

        if match_result.status == MatchResult.MATCH_FOUND and match_result.person:
            # Returning visitor
            person = match_result.person
            visitor_context = VisitorContext(
                name=person.name,
                recognition_status=VisitorStatus.RETURNING,
                company=person.company,
                role=person.role,
                visit_count=person.visit_count,
                last_visit=person.last_seen.isoformat() if person.last_seen else None
            )
            initial_state = ConversationState.GREETING_RETURNING

        else:
            # New visitor
            visitor_context = VisitorContext(
                recognition_status=VisitorStatus.NEW
            )
            initial_state = ConversationState.GREETING_NEW

        session = ConversationSession(
            session_id=session_id,
            state=initial_state,
            visitor_context=visitor_context,
            person_id=match_result.person.person_id if match_result.person else None
        )

        self.active_sessions[session_id] = session
        logger.info(
            "Conversation session started",
            session_id=session_id,
            state=initial_state.value,
            visitor_name=visitor_context.name
        )

        return session

    async def generate_greeting(
        self, session: ConversationSession
    ) -> str:
        """
        Generate the initial greeting for the visitor.

        Args:
            session: Active conversation session

        Returns:
            Greeting text
        """
        system_prompt = PromptBuilder.build_system_prompt(session.visitor_context)
        greeting_prompt = PromptBuilder.build_initial_greeting_prompt(
            session.visitor_context
        )

        response = await self.bedrock.generate_response(
            prompt=greeting_prompt,
            system_prompt=system_prompt,
            max_tokens=150,
            temperature=0.7
        )

        # Update session
        session.add_message("assistant", response)

        if session.state == ConversationState.GREETING_NEW:
            session.state = ConversationState.WAITING_FOR_NAME
        elif session.state == ConversationState.GREETING_RETURNING:
            session.state = ConversationState.ACTIVE_CONVERSATION

        logger.info(
            "Greeting generated",
            session_id=session.session_id,
            response_preview=response[:50]
        )

        return response

    async def process_user_input(
        self,
        session_id: str,
        user_text: str
    ) -> str:
        """
        Process user input and generate AI response.

        Args:
            session_id: Active session ID
            user_text: Transcribed user speech

        Returns:
            AI response text
        """
        session = self.active_sessions.get(session_id)
        if not session:
            logger.warning("Session not found", session_id=session_id)
            return "I'm sorry, could you please repeat that?"

        # Add user message to history
        session.add_message("user", user_text)

        # Handle based on current state
        if session.state == ConversationState.WAITING_FOR_NAME:
            return await self._handle_name_input(session, user_text)
        elif session.state == ConversationState.ASKING_CONSENT:
            return await self._handle_consent_response(session, user_text)
        else:
            return await self._handle_conversation(session, user_text)

    async def _handle_name_input(
        self, session: ConversationSession, user_text: str
    ) -> str:
        """Handle when we're waiting for the visitor's name."""
        # Extract name using Llama
        name_prompt = PromptBuilder.build_name_extraction_prompt(user_text)
        extracted_name = await self.bedrock.generate_response(
            prompt=name_prompt,
            max_tokens=20,
            temperature=0.1
        )

        extracted_name = extracted_name.strip().strip('"').strip("'")

        if extracted_name and extracted_name.upper() != "UNKNOWN":
            session.visitor_context.name = extracted_name
            
            # CHECK DATABASE: Is this a returning visitor?
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"http://localhost:5000/api/lookup-visitor/{extracted_name}", timeout=3)
                    data = resp.json()
                    if data.get("found"):
                        # RETURNING VISITOR!
                        visit_count = data.get("visit_count", 2)
                        session.state = ConversationState.ACTIVE_CONVERSATION
                        response = (
                            f"Welcome back, {extracted_name}! Great to see you again. "
                            f"You've visited us {visit_count} times now. How can I help you today?"
                        )
                        session.add_message("assistant", response)
                        return response
            except Exception:
                pass  # DB lookup failed, treat as new
            
            # NEW VISITOR - SAVE IMMEDIATELY (no consent asking)
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    # Call our own API to save - this definitely works
                    resp = await client.post(
                        "http://localhost:5000/api/face/register?name=" + extracted_name,
                        json={"image": ""},  # Empty image - just save name
                        timeout=5
                    )
                    logger.info("Save via API result", status=resp.status_code, body=resp.text[:100])
            except Exception as e:
                logger.error("Save via API failed", error=str(e))
            
            # Also try direct DB save as backup
            try:
                from database.database import AsyncSessionLocal
                if AsyncSessionLocal:
                    from sqlalchemy import text
                    async with AsyncSessionLocal() as db:
                        result = await db.execute(
                            text("SELECT id FROM visitor WHERE LOWER(name)=LOWER(:name)"),
                            {"name": extracted_name}
                        )
                        if not result.mappings().first():
                            await db.execute(
                                text("INSERT INTO visitor (name, consent_status, first_seen, last_seen) VALUES (:name, 'granted', NOW(), NOW())"),
                                {"name": extracted_name}
                            )
                            await db.commit()
                            logger.info("✅ VISITOR SAVED TO DB (direct)", name=extracted_name)
                        else:
                            logger.info("Visitor already exists in DB", name=extracted_name)
                else:
                    logger.error("AsyncSessionLocal is None!")
            except Exception as e:
                logger.error("Direct DB save failed", error=str(e))
            
            # Go straight to active conversation (no consent question)
            session.state = ConversationState.ACTIVE_CONVERSATION

            response = (
                f"Nice to meet you, {extracted_name}! Welcome to Code Origin.AI. "
                f"I'll remember you for next time. How can I help you today?"
            )
        else:
            response = (
                "I didn't quite catch your name. Could you please tell me your name?"
            )

        session.add_message("assistant", response)
        return response

    async def _handle_consent_response(
        self, session: ConversationSession, user_text: str
    ) -> str:
        """Handle the visitor's response to consent request."""
        positive_indicators = ["yes", "sure", "okay", "ok", "yeah", "yep", "please", "go ahead"]
        negative_indicators = ["no", "don't", "nope", "prefer not", "rather not"]

        user_lower = user_text.lower()

        if any(word in user_lower for word in positive_indicators):
            # Consent granted - SAVE TO DATABASE IMMEDIATELY
            session.visitor_context.recognition_status = VisitorStatus.NEW
            session.state = ConversationState.ACTIVE_CONVERSATION

            # SAVE NAME TO MySQL RIGHT NOW
            try:
                from database.database import AsyncSessionLocal
                if AsyncSessionLocal:
                    from sqlalchemy import text
                    async with AsyncSessionLocal() as db:
                        # Check if already exists
                        result = await db.execute(
                            text("SELECT id FROM visitor WHERE LOWER(name)=LOWER(:name)"),
                            {"name": session.visitor_context.name}
                        )
                        if not result.mappings().first():
                            await db.execute(
                                text("INSERT INTO visitor (name, consent_status, first_seen, last_seen) VALUES (:name, 'granted', NOW(), NOW())"),
                                {"name": session.visitor_context.name}
                            )
                            await db.commit()
                            import structlog
                            structlog.get_logger().info("✅ VISITOR SAVED TO DB", name=session.visitor_context.name)
            except Exception as e:
                import structlog
                structlog.get_logger().error("DB save in consent failed", error=str(e))

            response = (
                f"Thank you, {session.visitor_context.name}! "
                f"I'll remember you for next time. How can I help you today?"
            )
            # Signal to register face
            session.add_message("system", "CONSENT_GRANTED")

        elif any(word in user_lower for word in negative_indicators):
            # Consent denied
            session.state = ConversationState.ACTIVE_CONVERSATION
            response = (
                f"No problem at all, {session.visitor_context.name}! "
                f"Your privacy is important to us. How can I help you today?"
            )
            session.add_message("system", "CONSENT_DENIED")

        else:
            # Unclear response
            response = (
                "I just want to confirm - would you like me to remember your face "
                "for future visits? A simple yes or no is fine."
            )

        session.add_message("assistant", response)
        return response

    async def _handle_conversation(
        self, session: ConversationSession, user_text: str
    ) -> str:
        """Handle general conversation with the visitor."""
        system_prompt = PromptBuilder.build_system_prompt(session.visitor_context)
        user_prompt = PromptBuilder.build_conversation_prompt(
            session.visitor_context, user_text
        )

        response = await self.bedrock.generate_response(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=200,
            temperature=0.6
        )

        session.add_message("assistant", response)

        # Check for farewell indicators
        farewell_indicators = ["bye", "goodbye", "thanks", "thank you", "see you", "leaving"]
        if any(word in user_text.lower() for word in farewell_indicators):
            session.state = ConversationState.FAREWELL

        return response

    async def end_session(self, session_id: str) -> Optional[Dict]:
        """
        End a conversation session.

        Args:
            session_id: Session to end

        Returns:
            Session summary dict
        """
        session = self.active_sessions.pop(session_id, None)
        if not session:
            return None

        session.state = ConversationState.ENDED

        summary = {
            "session_id": session.session_id,
            "visitor_name": session.visitor_context.name,
            "message_count": len(session.messages),
            "started_at": session.started_at.isoformat(),
            "ended_at": datetime.utcnow().isoformat(),
            "state_reached": session.state.value
        }

        logger.info("Conversation session ended", **summary)
        return summary

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get an active session by ID."""
        return self.active_sessions.get(session_id)

    def get_active_session_count(self) -> int:
        """Get count of active sessions."""
        return len(self.active_sessions)
