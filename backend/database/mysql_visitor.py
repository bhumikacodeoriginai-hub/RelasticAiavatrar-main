"""
MySQL Visitor operations.
Stores visitor name, face data, visit history.
Recognizes returning visitors by name.
"""

from datetime import datetime
from typing import Optional, Dict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger()


class MySQLVisitorService:
    """Handles all visitor database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_visitor(
        self,
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        company: Optional[str] = None,
        consent_status: str = "granted"
    ) -> int:
        """Register a new visitor. Returns visitor ID."""
        result = await self.db.execute(
            text("""
                INSERT INTO visitor (name, email, phone, company, consent_status, first_seen, last_seen)
                VALUES (:name, :email, :phone, :company, :consent, NOW(), NOW())
            """),
            {"name": name, "email": email, "phone": phone, "company": company, "consent": consent_status}
        )
        await self.db.commit()
        
        # Get the inserted ID
        result = await self.db.execute(text("SELECT LAST_INSERT_ID()"))
        visitor_id = result.scalar()
        
        logger.info("Visitor registered", id=visitor_id, name=name)
        return visitor_id

    async def find_visitor_by_name(self, name: str) -> Optional[Dict]:
        """Find a visitor by name (case-insensitive)."""
        result = await self.db.execute(
            text("SELECT * FROM visitor WHERE LOWER(name) = LOWER(:name) LIMIT 1"),
            {"name": name}
        )
        row = result.mappings().first()
        if row:
            return dict(row)
        return None

    async def get_visitor_by_id(self, visitor_id: int) -> Optional[Dict]:
        """Get visitor by ID."""
        result = await self.db.execute(
            text("SELECT * FROM visitor WHERE id = :id"),
            {"id": visitor_id}
        )
        row = result.mappings().first()
        if row:
            return dict(row)
        return None

    async def update_last_seen(self, visitor_id: int) -> None:
        """Update last_seen and increment visit_count."""
        await self.db.execute(
            text("""
                UPDATE visitor 
                SET last_seen = NOW(), visit_count = visit_count + 1
                WHERE id = :id
            """),
            {"id": visitor_id}
        )
        await self.db.commit()
        logger.info("Visitor updated", id=visitor_id)

    async def log_visit(self, visitor_id: int, purpose: Optional[str] = None) -> int:
        """Log a new visit."""
        await self.db.execute(
            text("""
                INSERT INTO visits (visitor_id, arrival_time, purpose)
                VALUES (:vid, NOW(), :purpose)
            """),
            {"vid": visitor_id, "purpose": purpose}
        )
        await self.db.commit()
        result = await self.db.execute(text("SELECT LAST_INSERT_ID()"))
        return result.scalar()

    async def end_visit(self, visit_id: int) -> None:
        """Mark visit as ended."""
        await self.db.execute(
            text("UPDATE visits SET departure_time = NOW() WHERE id = :id"),
            {"id": visit_id}
        )
        await self.db.commit()

    async def save_conversation(self, visitor_id: int, role: str, message: str) -> None:
        """Save a conversation message."""
        await self.db.execute(
            text("""
                INSERT INTO conversations (visitor_id, role, message, timestamp)
                VALUES (:vid, :role, :msg, NOW())
            """),
            {"vid": visitor_id, "role": role, "msg": message}
        )
        await self.db.commit()

    async def get_all_visitors(self, limit: int = 50) -> list:
        """Get all registered visitors."""
        result = await self.db.execute(
            text("SELECT * FROM visitor ORDER BY last_seen DESC LIMIT :lim"),
            {"lim": limit}
        )
        return [dict(row) for row in result.mappings().all()]

    async def get_visitor_history(self, visitor_id: int) -> list:
        """Get conversation history for a visitor."""
        result = await self.db.execute(
            text("""
                SELECT role, message, timestamp 
                FROM conversations 
                WHERE visitor_id = :vid 
                ORDER BY timestamp DESC 
                LIMIT 20
            """),
            {"vid": visitor_id}
        )
        return [dict(row) for row in result.mappings().all()]

    async def get_today_visitors(self) -> list:
        """Get visitors from today."""
        result = await self.db.execute(
            text("""
                SELECT v.*, vs.arrival_time 
                FROM visitor v
                JOIN visits vs ON v.id = vs.visitor_id
                WHERE DATE(vs.arrival_time) = CURDATE()
                ORDER BY vs.arrival_time DESC
            """)
        )
        return [dict(row) for row in result.mappings().all()]

    async def delete_visitor(self, visitor_id: int) -> bool:
        """Delete visitor and all data (GDPR)."""
        await self.db.execute(
            text("DELETE FROM visitor WHERE id = :id"),
            {"id": visitor_id}
        )
        await self.db.commit()
        logger.info("Visitor deleted", id=visitor_id)
        return True
