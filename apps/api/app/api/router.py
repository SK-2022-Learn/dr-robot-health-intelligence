"""Top-level router for all version-one API endpoints."""

from fastapi import APIRouter

from app.api.routes.agents import router as agents_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.audit import router as audit_router
from app.api.routes.chat import router as chat_router
from app.api.routes.doctor_visit import router as doctor_visit_router
from app.api.routes.documents import router as documents_router
from app.api.routes.extraction import router as extraction_router
from app.api.routes.family import router as family_router
from app.api.routes.health import router as health_router
from app.api.routes.health_events import router as health_events_router
from app.api.routes.profile_data import router as profile_data_router
from app.api.routes.profiles import router as profiles_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.safety import router as safety_router
from app.api.routes.system import router as system_router
from app.api.routes.timeline import router as timeline_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(agents_router)
api_router.include_router(health_router)
api_router.include_router(family_router)
api_router.include_router(analytics_router)
api_router.include_router(profiles_router)
api_router.include_router(health_events_router)
api_router.include_router(audit_router)
api_router.include_router(chat_router)
api_router.include_router(timeline_router)
api_router.include_router(profile_data_router)
api_router.include_router(documents_router)
api_router.include_router(doctor_visit_router)
api_router.include_router(extraction_router)
api_router.include_router(retrieval_router)
api_router.include_router(safety_router)
api_router.include_router(system_router)
