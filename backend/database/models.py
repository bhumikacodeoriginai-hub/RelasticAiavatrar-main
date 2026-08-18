"""
SQLAlchemy ORM models for the AI Receptionist application.
Supports both SQLite (development) and PostgreSQL+pgvector (production).
"""

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime,
    ForeignKey, Boolean, JSON
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
import enum

from database.database import Base

# Use JSON column for embeddings (MySQL compatible)
EmbeddingColumn = lambda: Column(JSON, nullable=True)


class ConsentStatus(str, enum.Enum):
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"


class VisitStatus(str, enum.Enum):
    ARRIVED = "arrived"
    IN_MEETING = "in_meeting"
    DEPARTED = "departed"
    CANCELLED = "cancelled"


class EmployeeAvailability(str, enum.Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    AWAY = "away"
    OFFLINE = "offline"


class Person(Base):
    """Stores all recognized visitors."""
    __tablename__ = "persons"

    person_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    image_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    face_embedding = EmbeddingColumn()
    consent_status: Mapped[str] = mapped_column(
        String(20), default=ConsentStatus.PENDING.value
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )
    last_seen: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    visit_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    visits: Mapped[List["Visit"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    conversations: Mapped[List["Conversation"]] = relationship(back_populates="person")


class Employee(Base):
    """Internal office employees."""
    __tablename__ = "employees"

    employee_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    designation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    office_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    availability: Mapped[str] = mapped_column(
        String(20), default=EmployeeAvailability.AVAILABLE.value
    )
    face_embedding = EmbeddingColumn()
    created_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )


class Visit(Base):
    """Tracks each visit instance."""
    __tablename__ = "visits"

    visit_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persons.person_id", ondelete="CASCADE")
    )
    employee_to_meet: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("employees.employee_id"), nullable=True
    )
    arrival_time: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )
    departure_time: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=VisitStatus.ARRIVED.value
    )
    conversation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )

    # Relationships
    person: Mapped["Person"] = relationship(back_populates="visits")


class Conversation(Base):
    """Stores conversation sessions."""
    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    person_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("persons.person_id", ondelete="SET NULL"), nullable=True
    )
    session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )
    ended_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )

    # Relationships
    person: Mapped[Optional["Person"]] = relationship(back_populates="conversations")
    messages: Mapped[List["ConversationMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class ConversationMessage(Base):
    """Individual messages in a conversation."""
    __tablename__ = "conversation_messages"

    message_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.conversation_id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
