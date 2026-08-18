"""
Visitor API endpoints.
Handles visitor registration, lookup, consent management, and visit tracking.
"""

import uuid
import base64
from datetime import datetime
from typing import Optional, List

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from database.database import get_db
from database.visitors import VisitorRepository
from database.models import Person, Visit

logger = structlog.get_logger()

router = APIRouter(prefix="/api/visitors", tags=["visitors"])


# === Pydantic Schemas ===

class VisitorCreate(BaseModel):
    """Schema for creating a new visitor."""
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    consent_status: str = Field(default="pending")
    face_embedding: Optional[List[float]] = None


class VisitorResponse(BaseModel):
    """Schema for visitor response."""
    person_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    consent_status: str
    visit_count: int
    last_seen: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class VisitCreate(BaseModel):
    """Schema for creating a new visit."""
    person_id: str
    employee_to_meet: Optional[str] = None
    purpose: Optional[str] = None


class VisitResponse(BaseModel):
    """Schema for visit response."""
    visit_id: str
    person_id: str
    arrival_time: str
    departure_time: Optional[str] = None
    purpose: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class ConsentUpdate(BaseModel):
    """Schema for updating consent status."""
    consent_status: str = Field(..., pattern="^(granted|denied|revoked)$")


class VisitorStats(BaseModel):
    """Schema for visitor statistics."""
    visits_today: int
    active_visitors: int
    total_registered: int


# === Endpoints ===

@router.post("/register", response_model=VisitorResponse)
async def register_visitor(
    visitor: VisitorCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new visitor.
    Called after consent is granted and name is captured.
    """
    repo = VisitorRepository(db)

    # Convert face embedding if provided
    embedding = None
    if visitor.face_embedding:
        embedding = np.array(visitor.face_embedding, dtype=np.float32)

    person = await repo.create_person(
        name=visitor.name,
        face_embedding=embedding,
        email=visitor.email,
        phone=visitor.phone,
        company=visitor.company,
        role=visitor.role,
        consent_status=visitor.consent_status
    )

    await db.commit()

    logger.info("Visitor registered", person_id=str(person.person_id), name=person.name)

    return VisitorResponse(
        person_id=str(person.person_id),
        name=person.name,
        email=person.email,
        phone=person.phone,
        company=person.company,
        role=person.role,
        consent_status=person.consent_status,
        visit_count=person.visit_count,
        last_seen=person.last_seen.isoformat() if person.last_seen else None,
        created_at=person.created_at.isoformat()
    )


@router.get("/", response_model=List[VisitorResponse])
async def list_visitors(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List all registered visitors with pagination."""
    repo = VisitorRepository(db)
    persons = await repo.get_all_persons(limit=limit, offset=offset)

    return [
        VisitorResponse(
            person_id=str(p.person_id),
            name=p.name,
            email=p.email,
            phone=p.phone,
            company=p.company,
            role=p.role,
            consent_status=p.consent_status,
            visit_count=p.visit_count,
            last_seen=p.last_seen.isoformat() if p.last_seen else None,
            created_at=p.created_at.isoformat()
        )
        for p in persons
    ]


@router.get("/stats", response_model=VisitorStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get visitor statistics for the dashboard."""
    repo = VisitorRepository(db)
    stats = await repo.get_visit_stats()
    return VisitorStats(**stats)


@router.get("/{person_id}", response_model=VisitorResponse)
async def get_visitor(
    person_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific visitor by ID."""
    repo = VisitorRepository(db)
    person = await repo.get_person_by_id(uuid.UUID(person_id))

    if not person:
        raise HTTPException(status_code=404, detail="Visitor not found")

    return VisitorResponse(
        person_id=str(person.person_id),
        name=person.name,
        email=person.email,
        phone=person.phone,
        company=person.company,
        role=person.role,
        consent_status=person.consent_status,
        visit_count=person.visit_count,
        last_seen=person.last_seen.isoformat() if person.last_seen else None,
        created_at=person.created_at.isoformat()
    )


@router.put("/{person_id}/consent", response_model=dict)
async def update_consent(
    person_id: str,
    consent: ConsentUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update visitor consent status.
    If revoked, removes face embedding and image data (GDPR compliance).
    """
    repo = VisitorRepository(db)
    person = await repo.get_person_by_id(uuid.UUID(person_id))

    if not person:
        raise HTTPException(status_code=404, detail="Visitor not found")

    if consent.consent_status == "revoked":
        await repo.revoke_consent(uuid.UUID(person_id))
        await db.commit()
        return {"message": "Consent revoked. Biometric data has been deleted."}
    else:
        person.consent_status = consent.consent_status
        await db.commit()
        return {"message": f"Consent status updated to: {consent.consent_status}"}


@router.delete("/{person_id}")
async def delete_visitor(
    person_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a visitor and all associated data.
    This is a permanent action for privacy/GDPR compliance.
    """
    repo = VisitorRepository(db)
    success = await repo.delete_person(uuid.UUID(person_id))

    if not success:
        raise HTTPException(status_code=404, detail="Visitor not found")

    await db.commit()
    return {"message": "Visitor and all associated data have been deleted."}


@router.post("/visits", response_model=VisitResponse)
async def create_visit(
    visit: VisitCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new visit record."""
    repo = VisitorRepository(db)

    employee_id = uuid.UUID(visit.employee_to_meet) if visit.employee_to_meet else None

    new_visit = await repo.create_visit(
        person_id=uuid.UUID(visit.person_id),
        employee_to_meet=employee_id,
        purpose=visit.purpose
    )

    await db.commit()

    return VisitResponse(
        visit_id=str(new_visit.visit_id),
        person_id=str(new_visit.person_id),
        arrival_time=new_visit.arrival_time.isoformat(),
        departure_time=None,
        purpose=new_visit.purpose,
        status=new_visit.status
    )


@router.put("/visits/{visit_id}/end")
async def end_visit(
    visit_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Mark a visit as ended/departed."""
    repo = VisitorRepository(db)
    await repo.end_visit(uuid.UUID(visit_id))
    await db.commit()
    return {"message": "Visit ended successfully"}


@router.get("/visits/active", response_model=List[VisitResponse])
async def get_active_visits(db: AsyncSession = Depends(get_db)):
    """Get all currently active visits."""
    repo = VisitorRepository(db)
    visits = await repo.get_active_visits()

    return [
        VisitResponse(
            visit_id=str(v.visit_id),
            person_id=str(v.person_id),
            arrival_time=v.arrival_time.isoformat(),
            departure_time=v.departure_time.isoformat() if v.departure_time else None,
            purpose=v.purpose,
            status=v.status
        )
        for v in visits
    ]
