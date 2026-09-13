"""Explicit domain values shared by persistence and API contracts."""

from enum import StrEnum


class ProvenanceType(StrEnum):
    DOCUMENT_VERIFIED = "DOCUMENT_VERIFIED"
    USER_REPORTED = "USER_REPORTED"
    DEVICE_MEASURED = "DEVICE_MEASURED"
    AI_EXTRACTED = "AI_EXTRACTED"
    AI_DERIVED = "AI_DERIVED"
    USER_CORRECTED = "USER_CORRECTED"


class VerificationStatus(StrEnum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class DocumentStatus(StrEnum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PARSED = "PARSED"
    NEEDS_OCR = "NEEDS_OCR"
    FAILED = "FAILED"


class VectorIndexStatus(StrEnum):
    NOT_INDEXED = "NOT_INDEXED"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    INDEX_FAILED = "INDEX_FAILED"


class RelationshipType(StrEnum):
    SELF = "SELF"
    MOTHER = "MOTHER"
    FATHER = "FATHER"
    SIBLING = "SIBLING"
    CHILD = "CHILD"
    GRANDMOTHER = "GRANDMOTHER"
    GRANDFATHER = "GRANDFATHER"
    OTHER = "OTHER"


class CandidateStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    CORRECTED = "CORRECTED"
    REJECTED = "REJECTED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"


class CandidateType(StrEnum):
    CONDITION = "condition"
    MEDICATION = "medication"
    LAB = "lab"
    SYMPTOM = "symptom"
    MEASUREMENT = "measurement"


class AccessLevel(StrEnum):
    PRIVATE = "PRIVATE"
    CAREGIVER = "CAREGIVER"
    FAMILY_SUMMARY = "FAMILY_SUMMARY"
    FULL = "FULL"


class HealthEventType(StrEnum):
    CONDITION = "CONDITION"
    MEDICATION = "MEDICATION"
    LAB = "LAB"
    PROCEDURE = "PROCEDURE"
    SYMPTOM = "SYMPTOM"
    MEASUREMENT = "MEASUREMENT"
    HOSPITALIZATION = "HOSPITALIZATION"
    ALLERGY = "ALLERGY"
    IMMUNIZATION = "IMMUNIZATION"
    LIFESTYLE = "LIFESTYLE"
    FAMILY_HISTORY = "FAMILY_HISTORY"
    NOTE = "NOTE"


class MessageRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class PendingHealthEntryStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
