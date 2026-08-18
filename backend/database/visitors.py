"""
Database operations for visitors/persons.
Handles CRUD and face embedding search.
Uses numpy cosine similarity for SQLite, pgvector for PostgreSQL.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Tuple

import numpy as np
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from database.models import Person, Visit, Conversation, ConversationMessage

logger = structlog.get_logger()


class VisitorRepository:
    """Repository pattern for visitor database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_person(
        self,
        name: str,
        face_embedding: Optional[np.ndarray] = None,
        image_path: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        company: Optional[str] = None,
        role: Optional[str] = None,
        consent_status: str = "pending"
    ) -> Person:
        """Create a new person record."""
        # Convert embedding to list for JSON storage
        embedding_data = face_embedding.tolist() if face_embedding is not None else None

        person = Person(
            person_id=str(uuid.uuid4()),
            name=name,
            email=email,
            phone=phone,
            company=company,
            role=role,
            image_path=image_path,
            face_embedding=embedding_data,
            consent_status=consent_status,
            last_seen=datetime.utcnow().isoformat(),
            visit_count=1
        )
        self.db.add(person)
        await self.db.flush()
        logger.info("Created new person", person_id=person.person_id, name=name)
        return person

    async def get_person_by_id(self, person_id) -> Optional[Person]:
        """Get a person by their ID."""
        pid = str(person_id)
        result = await self.db.execute(
            select(Person).where(Person.person_id == pid)
        )
        return result.scalar_one_or_none()

    async def search_by_face(
        self,
        embedding: np.ndarray,
        threshold: float = 0.6,
        limit: int = 5
    ) -> List[Tuple[Person, float]]:
        """
        Search for a person by face embedding using cosine similarity.
        Uses in-memory numpy comparison for SQLite.
        Returns list of (person, similarity_score) tuples.
        """
        # Get all persons with face embeddings
        result = await self.db.execute(
            select(Person)
            .where(Person.face_embedding.isnot(None))
            .where(Person.consent_status == "granted")
        )
        persons = list(result.scalars().all())

        if not persons:
            return []

        # Compute cosine similarity against each stored embedding
        matches = []
        query_norm = embedding / np.linalg.norm(embedding)

        for person in persons:
            stored = person.face_embedding
            if stored is None:
                continue

            stored_arr = np.array(stored, dtype=np.float32)
            stored_norm = stored_arr / np.linalg.norm(stored_arr)
            similarity = float(np.dot(query_norm, stored_norm))

            if similarity >= threshold:
                matches.append((person, similarity))

        # Sort by similarity (highest first)
        matches.sort(key=lambda x: x[1], reverse=True)

        logger.info(
            "Face search completed",
            matches_found=len(matches),
            threshold=threshold,
            total_checked=len(persons)
        )
        return matches[:limit]

    async def update_last_seen(self, person_id) -> None:
        """Update the last_seen timestamp and increment visit count."""
        pid = str(person_id)
        person = await self.get_person_by_id(pid)
        if person:
            person.last_seen = datetime.utcnow().isoformat()
            person.visit_count = (person.visit_count or 0) + 1

    async def create_visit(
        self,
        person_id,
        employee_to_meet=None,
        purpose: Optional[str] = None
    ) -> Visit:
        """Create a new visit record."""
        visit = Visit(
            visit_id=str(uuid.uuid4()),
            person_id=str(person_id),
            employee_to_meet=str(employee_to_meet) if employee_to_meet else None,
            purpose=purpose,
        )
        self.db.add(visit)
        await self.db.flush()
        logger.info("Created visit", visit_id=visit.visit_id, person_id=str(person_id))
        return visit

    async def end_visit(self, visit_id) -> None:
        """Mark a visit as departed."""
        vid = str(visit_id)
        result = await self.db.execute(
            select(Visit).where(Visit.visit_id == vid)
        )
        visit = result.scalar_one_or_none()
        if visit:
            visit.departure_time = datetime.utcnow().isoformat()
            visit.status = "departed"

    async def get_active_visits(self) -> List[Visit]:
        """Get all currently active visits."""
        result = await self.db.execute(
            select(Visit)
            .where(Visit.departure_time.is_(None))
            .order_by(Visit.arrival_time.desc())
        )
        return list(result.scalars().all())

    async def get_today_visits(self) -> List[Visit]:
        """Get all visits from today."""
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        result = await self.db.execute(
            select(Visit)
            .where(Visit.arrival_time.like(f"{today_str}%"))
            .order_by(Visit.arrival_time.desc())
        )
        return list(result.scalars().all())

    async def delete_person(self, person_id) -> bool:
        """Delete a person and all associated data (GDPR compliance)."""
        person = await self.get_person_by_id(str(person_id))
        if person:
            await self.db.delete(person)
            logger.info("Deleted person", person_id=str(person_id))
            return True
        return False

    async def revoke_consent(self, person_id) -> None:
        """Revoke consent and remove biometric data."""
        person = await self.get_person_by_id(str(person_id))
        if person:
            person.consent_status = "revoked"
            person.face_embedding = None
            person.image_path = None
            logger.info("Revoked consent", person_id=str(person_id))

    async def get_all_persons(self, limit: int = 100, offset: int = 0) -> List[Person]:
        """Get all persons with pagination."""
        result = await self.db.execute(
            select(Person)
            .order_by(Person.last_seen.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_visit_stats(self) -> dict:
        """Get visitor statistics."""
        today_str = datetime.utcnow().strftime("%Y-%m-%d")

        total_today = await self.db.execute(
            select(func.count(Visit.visit_id))
            .where(Visit.arrival_time.like(f"{today_str}%"))
        )
        active = await self.db.execute(
            select(func.count(Visit.visit_id))
            .where(Visit.departure_time.is_(None))
        )
        total_persons = await self.db.execute(
            select(func.count(Person.person_id))
        )

        return {
            "visits_today": total_today.scalar_one(),
            "active_visitors": active.scalar_one(),
            "total_registered": total_persons.scalar_one()
        }
