"""
API routes for the AI Avatar Receptionist.
"""

from api.visitor import router as visitor_router
from api.conversation import router as conversation_router
from api.employee import router as employee_router
from api.websocket import router as websocket_router
from api.dashboard import router as dashboard_router

__all__ = [
    "visitor_router",
    "conversation_router",
    "employee_router",
    "websocket_router",
    "dashboard_router",
]
