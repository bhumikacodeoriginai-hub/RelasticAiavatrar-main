"""
Database seed script.
Adds sample employees on first run.
Run automatically when the app starts if the database is empty.
"""

import uuid
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from database.models import Employee

logger = structlog.get_logger()

SAMPLE_EMPLOYEES = [
    {
        "name": "Mr. Sharma",
        "email": "sharma@codeorigin.ai",
        "phone": "+91-9876543210",
        "department": "Management",
        "designation": "Director",
        "office_location": "Room 101",
        "availability": "available"
    },
    {
        "name": "Priya Patel",
        "email": "priya@codeorigin.ai",
        "phone": "+91-9876543211",
        "department": "Engineering",
        "designation": "Tech Lead",
        "office_location": "Room 205",
        "availability": "available"
    },
    {
        "name": "Arun Kumar",
        "email": "arun@codeorigin.ai",
        "phone": "+91-9876543212",
        "department": "Engineering",
        "designation": "Senior Developer",
        "office_location": "Room 206",
        "availability": "available"
    },
    {
        "name": "Sneha Gupta",
        "email": "sneha@codeorigin.ai",
        "phone": "+91-9876543213",
        "department": "HR",
        "designation": "HR Manager",
        "office_location": "Room 103",
        "availability": "available"
    },
    {
        "name": "Rajesh Mehta",
        "email": "rajesh@codeorigin.ai",
        "phone": "+91-9876543214",
        "department": "Sales",
        "designation": "Sales Director",
        "office_location": "Room 301",
        "availability": "available"
    }
]


async def seed_database(db: AsyncSession) -> None:
    """Seed the database with sample data if empty."""
    # Check if employees already exist
    result = await db.execute(select(func.count(Employee.employee_id)))
    count = result.scalar_one()

    if count > 0:
        logger.info("Database already seeded", employees=count)
        return

    logger.info("Seeding database with sample employees...")

    for emp_data in SAMPLE_EMPLOYEES:
        employee = Employee(
            employee_id=str(uuid.uuid4()),
            **emp_data,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )
        db.add(employee)

    await db.commit()
    logger.info("Database seeded successfully", employees_added=len(SAMPLE_EMPLOYEES))
