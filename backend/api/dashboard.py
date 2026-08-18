"""
Dashboard API endpoints.
Provides management dashboard data and statistics.
"""

from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from database.database import get_db
from database.models import Person, Visit, Employee, Conversation

logger = structlog.get_logger()

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# === Pydantic Schemas ===

class DashboardStats(BaseModel):
    """Overall dashboard statistics."""
    total_visitors_today: int
    new_visitors_today: int
    returning_visitors_today: int
    active_visitors: int
    total_registered: int
    total_employees: int
    active_conversations: int


class RecentVisitor(BaseModel):
    """A recent visitor entry for the dashboard."""
    person_id: str
    name: str
    company: Optional[str] = None
    arrival_time: str
    status: str
    visit_type: str  # 'new' or 'returning'


class SystemStatus(BaseModel):
    """System health status."""
    camera_active: bool
    ai_service_active: bool
    tts_active: bool
    database_active: bool
    uptime_seconds: float


# === Endpoints ===

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive dashboard statistics."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Total visits today
    total_today_result = await db.execute(
        select(func.count(Visit.visit_id))
        .where(Visit.arrival_time >= today_start)
    )
    total_today = total_today_result.scalar_one()

    # Active visitors (not departed)
    active_result = await db.execute(
        select(func.count(Visit.visit_id))
        .where(Visit.departure_time.is_(None))
    )
    active_visitors = active_result.scalar_one()

    # New visitors today (first-time, visit_count=1)
    new_today_result = await db.execute(
        select(func.count(Person.person_id))
        .where(Person.created_at >= today_start)
    )
    new_today = new_today_result.scalar_one()

    # Total registered persons
    total_registered_result = await db.execute(
        select(func.count(Person.person_id))
    )
    total_registered = total_registered_result.scalar_one()

    # Total employees
    total_employees_result = await db.execute(
        select(func.count(Employee.employee_id))
    )
    total_employees = total_employees_result.scalar_one()

    # Active conversations
    conv_manager = request.app.state.conversation_manager
    active_conversations = conv_manager.get_active_session_count()

    return DashboardStats(
        total_visitors_today=total_today,
        new_visitors_today=new_today,
        returning_visitors_today=max(0, total_today - new_today),
        active_visitors=active_visitors,
        total_registered=total_registered,
        total_employees=total_employees,
        active_conversations=active_conversations
    )


@router.get("/recent-visitors", response_model=List[RecentVisitor])
async def get_recent_visitors(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Get recent visitors for the dashboard feed."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(Visit, Person)
        .join(Person, Visit.person_id == Person.person_id)
        .where(Visit.arrival_time >= today_start)
        .order_by(Visit.arrival_time.desc())
        .limit(limit)
    )
    rows = result.all()

    visitors = []
    for visit, person in rows:
        visit_type = "new" if person.visit_count <= 1 else "returning"
        visitors.append(RecentVisitor(
            person_id=str(person.person_id),
            name=person.name,
            company=person.company,
            arrival_time=visit.arrival_time.isoformat(),
            status=visit.status,
            visit_type=visit_type
        ))

    return visitors


@router.get("/system-status", response_model=SystemStatus)
async def get_system_status(request: Request):
    """Get system health status."""
    app = request.app

    # Check services
    camera_active = (
        hasattr(app.state, 'camera_service') and
        app.state.camera_service.is_running
    ) if hasattr(app.state, 'camera_service') else False

    ai_active = hasattr(app.state, 'bedrock_client') and app.state.bedrock_client._initialized
    tts_active = hasattr(app.state, 'tts') and app.state.tts._initialized
    db_active = True  # If we got here, DB is working

    uptime = 0.0
    if hasattr(app.state, 'start_time'):
        uptime = (datetime.utcnow() - app.state.start_time).total_seconds()

    return SystemStatus(
        camera_active=camera_active,
        ai_service_active=ai_active,
        tts_active=tts_active,
        database_active=db_active,
        uptime_seconds=uptime
    )
