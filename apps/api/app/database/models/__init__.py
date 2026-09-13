"""Import every mapped class so Alembic receives complete metadata."""

from app.database.models.audit_log import AuditLog
from app.database.models.consent_permission import ConsentPermission
from app.database.models.conversation import Conversation
from app.database.models.document_page import DocumentPage
from app.database.models.evidence_link import EvidenceLink
from app.database.models.extracted_candidate import ExtractedCandidate
from app.database.models.family_relationship import FamilyRelationship
from app.database.models.health_event import HealthEvent
from app.database.models.health_profile import HealthProfile
from app.database.models.medication import Medication
from app.database.models.message import Message
from app.database.models.observation import Observation
from app.database.models.pending_health_entry import PendingHealthEntry
from app.database.models.source_document import SourceDocument
from app.database.models.symptom import Symptom
from app.database.models.user import User

__all__ = [
    "AuditLog",
    "ConsentPermission",
    "Conversation",
    "DocumentPage",
    "EvidenceLink",
    "ExtractedCandidate",
    "FamilyRelationship",
    "HealthEvent",
    "HealthProfile",
    "Medication",
    "Message",
    "Observation",
    "PendingHealthEntry",
    "SourceDocument",
    "Symptom",
    "User",
]
