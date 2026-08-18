"""
Employee API endpoints.
Handles employee directory and availability management.
"""

import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from database.database import get_db
from database.models import Employee

logger = structlog.get_logger()

router = APIRouter(prefix="/api/employees", tags=["employees"])


# === Pydantic Schemas ===

class EmployeeCreate(BaseModel):
    """Schema for creating an employee."""
    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., max_length=255)
    phone: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    office_location: Optional[str] = None
    availability: str = Field(default="available")


class EmployeeResponse(BaseModel):
    """Schema for employee response."""
    employee_id: str
    name: str
    email: str
    phone: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    office_location: Optional[str] = None
    availability: str

    class Config:
        from_attributes = True


class AvailabilityUpdate(BaseModel):
    """Schema for updating availability."""
    availability: str = Field(..., pattern="^(available|busy|away|offline)$")


# === Endpoints ===

@router.get("/", response_model=List[EmployeeResponse])
async def list_employees(
    department: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all employees, optionally filtered by department."""
    query = select(Employee)
    if department:
        query = query.where(Employee.department == department)
    query = query.order_by(Employee.name)

    result = await db.execute(query)
    employees = result.scalars().all()

    return [
        EmployeeResponse(
            employee_id=str(e.employee_id),
            name=e.name,
            email=e.email,
            phone=e.phone,
            department=e.department,
            designation=e.designation,
            office_location=e.office_location,
            availability=e.availability
        )
        for e in employees
    ]


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific employee by ID."""
    result = await db.execute(
        select(Employee).where(Employee.employee_id == uuid.UUID(employee_id))
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    return EmployeeResponse(
        employee_id=str(employee.employee_id),
        name=employee.name,
        email=employee.email,
        phone=employee.phone,
        department=employee.department,
        designation=employee.designation,
        office_location=employee.office_location,
        availability=employee.availability
    )


@router.post("/", response_model=EmployeeResponse)
async def create_employee(
    employee: EmployeeCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new employee record."""
    new_employee = Employee(
        employee_id=uuid.uuid4(),
        name=employee.name,
        email=employee.email,
        phone=employee.phone,
        department=employee.department,
        designation=employee.designation,
        office_location=employee.office_location,
        availability=employee.availability
    )

    db.add(new_employee)
    await db.commit()

    logger.info("Employee created", employee_id=str(new_employee.employee_id))

    return EmployeeResponse(
        employee_id=str(new_employee.employee_id),
        name=new_employee.name,
        email=new_employee.email,
        phone=new_employee.phone,
        department=new_employee.department,
        designation=new_employee.designation,
        office_location=new_employee.office_location,
        availability=new_employee.availability
    )


@router.put("/{employee_id}/availability")
async def update_availability(
    employee_id: str,
    avail: AvailabilityUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an employee's availability status."""
    result = await db.execute(
        select(Employee).where(Employee.employee_id == uuid.UUID(employee_id))
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    await db.execute(
        update(Employee)
        .where(Employee.employee_id == uuid.UUID(employee_id))
        .values(availability=avail.availability)
    )
    await db.commit()

    return {"message": f"Availability updated to: {avail.availability}"}


@router.get("/search/{name}", response_model=List[EmployeeResponse])
async def search_employee(
    name: str,
    db: AsyncSession = Depends(get_db)
):
    """Search for employees by name (partial match)."""
    result = await db.execute(
        select(Employee)
        .where(Employee.name.ilike(f"%{name}%"))
        .order_by(Employee.name)
    )
    employees = result.scalars().all()

    return [
        EmployeeResponse(
            employee_id=str(e.employee_id),
            name=e.name,
            email=e.email,
            phone=e.phone,
            department=e.department,
            designation=e.designation,
            office_location=e.office_location,
            availability=e.availability
        )
        for e in employees
    ]


@router.get("/available/list", response_model=List[EmployeeResponse])
async def list_available_employees(db: AsyncSession = Depends(get_db)):
    """List all currently available employees."""
    result = await db.execute(
        select(Employee)
        .where(Employee.availability == "available")
        .order_by(Employee.name)
    )
    employees = result.scalars().all()

    return [
        EmployeeResponse(
            employee_id=str(e.employee_id),
            name=e.name,
            email=e.email,
            phone=e.phone,
            department=e.department,
            designation=e.designation,
            office_location=e.office_location,
            availability=e.availability
        )
        for e in employees
    ]
