"""Extraction orchestration and transactional human review."""

import logging
from datetime import UTC, date, datetime, time
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.database.base import utc_now
from app.database.enums import (
    CandidateStatus,
    CandidateType,
    DocumentStatus,
    HealthEventType,
    ProvenanceType,
    VerificationStatus,
)
from app.database.models import (
    EvidenceLink,
    ExtractedCandidate,
    HealthEvent,
    Medication,
    Observation,
    SourceDocument,
    Symptom,
)
from app.extraction.prompts import build_extraction_prompt
from app.extraction.schemas import (
    ConditionCandidate,
    DocumentExtractionResult,
    LabCandidate,
    MeasurementCandidate,
    MedicationCandidate,
    SymptomCandidate,
)
from app.extraction.validator import validate_extraction
from app.llm.base import LLMProvider
from app.llm.factory import get_llm_provider
from app.llm.types import LLMError, LLMResponseError, LLMUnavailableError
from app.repositories.candidate import CandidateRepository
from app.repositories.document import DocumentRepository
from app.schemas.candidate import (
    CandidateCorrectionRequest,
    CandidateDetail,
    CandidateReviewResult,
    ExtractionSummary,
    TrustedRecordReference,
)
from app.services.audit import AuditService

logger = logging.getLogger("dr_robot.extraction")

CandidateSchema = (
    ConditionCandidate
    | MedicationCandidate
    | LabCandidate
    | SymptomCandidate
    | MeasurementCandidate
)


def _normalized_evidence(value: str) -> str:
    return " ".join(value.casefold().split())


def _ground_candidate_evidence(
    result: DocumentExtractionResult,
    pages: list[Any],
    fallback_text: str | None,
) -> None:
    """Require every quoted passage to exist in its attributed source page."""

    candidates: list[CandidateSchema] = [
        *result.conditions,
        *result.medications,
        *result.labs,
        *result.symptoms,
        *result.measurements,
    ]
    normalized_pages = {page.page_number: _normalized_evidence(page.text) for page in pages}
    fallback = _normalized_evidence(fallback_text or "")
    for candidate in candidates:
        evidence = _normalized_evidence(candidate.evidence_text)
        if candidate.page_number is not None:
            source = normalized_pages.get(candidate.page_number)
            if source is None or evidence not in source:
                raise LLMResponseError("Candidate evidence did not match its source page.")
            continue
        matching_pages = [number for number, text in normalized_pages.items() if evidence in text]
        if matching_pages:
            candidate.page_number = matching_pages[0]
        elif not normalized_pages and evidence in fallback:
            continue
        else:
            raise LLMResponseError("Candidate evidence was not found in the source document.")


SCHEMAS_BY_TYPE: dict[CandidateType, type[CandidateSchema]] = {
    CandidateType.CONDITION: ConditionCandidate,
    CandidateType.MEDICATION: MedicationCandidate,
    CandidateType.LAB: LabCandidate,
    CandidateType.SYMPTOM: SymptomCandidate,
    CandidateType.MEASUREMENT: MeasurementCandidate,
}


def _safe_candidate_state(candidate: ExtractedCandidate) -> dict[str, Any]:
    values = {
        key: value
        for key, value in candidate.structured_data.items()
        if key not in {"evidence_text"}
    }
    return {
        "candidate_type": candidate.candidate_type,
        "status": candidate.status.value,
        "structured_data": values,
        "confidence": candidate.confidence,
    }


def _as_datetime(value: date | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=UTC)
    return None


class ExtractionService:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        documents: DocumentRepository | None = None,
        candidates: CandidateRepository | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.provider = provider
        self.documents = documents or DocumentRepository()
        self.candidates = candidates or CandidateRepository()
        self.audit = audit or AuditService()

    def _require_document(self, db: Session, document_id: str) -> SourceDocument:
        document = self.documents.get(db, document_id)
        if document is None:
            raise ApiError(
                status_code=404,
                code="DOCUMENT_NOT_FOUND",
                message="Source document was not found.",
            )
        return document

    def _require_candidate(self, db: Session, candidate_id: str) -> ExtractedCandidate:
        candidate = self.candidates.get(db, candidate_id)
        if candidate is None:
            raise ApiError(
                status_code=404,
                code="CANDIDATE_NOT_FOUND",
                message="Extraction candidate was not found.",
            )
        return candidate

    @staticmethod
    def _summary(
        document_id: str, rows: list[ExtractedCandidate], *, reused: bool
    ) -> ExtractionSummary:
        by_type = {candidate_type.value: 0 for candidate_type in CandidateType}
        for row in rows:
            by_type[row.candidate_type] = by_type.get(row.candidate_type, 0) + 1
        return ExtractionSummary(
            document_id=document_id,
            candidate_count=len(rows),
            by_type=by_type,
            reused_existing=reused,
        )

    @staticmethod
    def detail(candidate: ExtractedCandidate) -> CandidateDetail:
        return CandidateDetail(
            id=candidate.id,
            document_id=candidate.document_id,
            candidate_type=candidate.candidate_type,
            structured_data=candidate.structured_data,
            confidence=candidate.confidence or 0,
            status=candidate.status,
            evidence_text=candidate.raw_text,
            page_number=candidate.structured_data.get("page_number"),
            reviewed_by_user_id=candidate.reviewed_by_user_id,
            reviewed_at=candidate.reviewed_at,
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
        )

    def _audit_failure(
        self, db: Session, document: SourceDocument, error_code: str, error_type: str
    ) -> None:
        self.audit.append(
            db,
            action="DOCUMENT_EXTRACTION_FAILED",
            entity_type="source_document",
            entity_id=document.id,
            actor_user_id=document.profile.owner_user_id,
            after_state={"error_code": error_code, "error_type": error_type},
        )
        db.commit()

    def extract(self, db: Session, document_id: str) -> ExtractionSummary:
        document = self._require_document(db, document_id)
        if document.status != DocumentStatus.PARSED or not document.has_extracted_text:
            raise ApiError(
                status_code=422,
                code="DOCUMENT_NOT_PARSED",
                message="The document must contain parsed text before extraction.",
            )
        existing = self.candidates.list_for_document(db, document_id)
        if existing:
            return self._summary(document_id, existing, reused=True)

        self.audit.append(
            db,
            action="DOCUMENT_EXTRACTION_STARTED",
            entity_type="source_document",
            entity_id=document.id,
            actor_user_id=document.profile.owner_user_id,
            after_state={"page_count": document.page_count},
        )
        db.commit()

        pages = self.documents.list_pages(db, document_id)
        prompt = build_extraction_prompt(pages, document.extracted_text)
        try:
            raw_response = self.provider.generate_structured(
                prompt, DocumentExtractionResult.model_json_schema()
            )
            result = validate_extraction(raw_response)
            _ground_candidate_evidence(result, pages, document.extracted_text)
        except LLMUnavailableError as error:
            self._audit_failure(db, document, "LLM_UNAVAILABLE", type(error).__name__)
            logger.warning(
                "Document extraction provider unavailable", extra={"document_id": document.id}
            )
            raise ApiError(
                status_code=503,
                code="LLM_UNAVAILABLE",
                message="Structured extraction is temporarily unavailable.",
            ) from error
        except LLMError as error:
            self._audit_failure(db, document, "INVALID_MODEL_OUTPUT", type(error).__name__)
            logger.warning(
                "Document extraction output rejected", extra={"document_id": document.id}
            )
            raise ApiError(
                status_code=502,
                code="STRUCTURED_EXTRACTION_FAILED",
                message="Structured extraction could not be completed.",
            ) from error
        except Exception as error:
            self._audit_failure(db, document, "EXTRACTION_ERROR", type(error).__name__)
            logger.exception(
                "Unexpected document extraction failure", extra={"document_id": document.id}
            )
            raise ApiError(
                status_code=502,
                code="STRUCTURED_EXTRACTION_FAILED",
                message="Structured extraction could not be completed.",
            ) from error

        rows: list[ExtractedCandidate] = []
        groups: tuple[tuple[CandidateType, list[CandidateSchema]], ...] = (
            (CandidateType.CONDITION, list(result.conditions)),
            (CandidateType.MEDICATION, list(result.medications)),
            (CandidateType.LAB, list(result.labs)),
            (CandidateType.SYMPTOM, list(result.symptoms)),
            (CandidateType.MEASUREMENT, list(result.measurements)),
        )
        for candidate_type, extracted in groups:
            for item in extracted:
                row = ExtractedCandidate(
                    document_id=document.id,
                    candidate_type=candidate_type.value,
                    raw_text=item.evidence_text,
                    structured_data=item.model_dump(mode="json"),
                    confidence=item.confidence,
                    status=CandidateStatus.PENDING,
                )
                rows.append(self.candidates.create(db, row))

        self.audit.append(
            db,
            action="DOCUMENT_EXTRACTION_COMPLETED",
            entity_type="source_document",
            entity_id=document.id,
            actor_user_id=document.profile.owner_user_id,
            after_state={
                "candidate_count": len(rows),
                "by_type": self._summary(document_id, rows, reused=False).by_type,
                "warning_count": len(result.warnings),
            },
        )
        db.commit()
        for row in rows:
            db.refresh(row)
        return self._summary(document_id, rows, reused=False)

    def list_candidates(
        self,
        db: Session,
        document_id: str,
        status: CandidateStatus | None = None,
    ) -> list[CandidateDetail]:
        self._require_document(db, document_id)
        return [
            self.detail(candidate)
            for candidate in self.candidates.list_for_document(db, document_id, status)
        ]

    def _validated_candidate(
        self,
        candidate: ExtractedCandidate,
        correction: CandidateCorrectionRequest | None = None,
    ) -> CandidateSchema:
        try:
            candidate_type = CandidateType(candidate.candidate_type)
            schema = SCHEMAS_BY_TYPE[candidate_type]
            values = dict(candidate.structured_data)
            if correction is not None:
                values.update(correction.structured_data)
                for immutable in ("evidence_text", "page_number", "confidence"):
                    values[immutable] = candidate.structured_data.get(immutable)
            return schema.model_validate(values)
        except (ValueError, ValidationError) as error:
            raise ApiError(
                status_code=422,
                code="INVALID_CANDIDATE_DATA",
                message="Candidate values did not match the required schema.",
            ) from error

    @staticmethod
    def _reviewable(candidate: ExtractedCandidate) -> None:
        if candidate.status != CandidateStatus.PENDING:
            raise ApiError(
                status_code=409,
                code="CANDIDATE_NOT_REVIEWABLE",
                message="Only pending candidates can be reviewed.",
            )

    @staticmethod
    def _required_observed_at(value: date | datetime | None, document: SourceDocument) -> datetime:
        observed = _as_datetime(value) or _as_datetime(document.document_date)
        if observed is None:
            raise ApiError(
                status_code=422,
                code="CANDIDATE_REQUIRES_CORRECTION",
                message="Add an explicit observation date before accepting this candidate.",
            )
        return observed

    def _create_trusted(
        self,
        db: Session,
        candidate: ExtractedCandidate,
        values: CandidateSchema,
        provenance: ProvenanceType,
    ) -> TrustedRecordReference:
        document = candidate.document
        verified = VerificationStatus.VERIFIED
        target: HealthEvent | Observation | Medication | Symptom

        if isinstance(values, ConditionCandidate):
            event_date = values.onset_date or document.document_date
            if event_date is None:
                raise ApiError(
                    status_code=422,
                    code="CANDIDATE_REQUIRES_CORRECTION",
                    message="Add an explicit condition date before accepting this candidate.",
                )
            target = HealthEvent(
                profile_id=document.profile_id,
                event_type=HealthEventType.CONDITION,
                event_date=event_date,
                end_date=values.resolved_date,
                title=values.condition_name,
                description=values.status,
                verification_status=verified,
                provenance=provenance,
                confidence=values.confidence,
                source_document_id=document.id,
                created_by_user_id=document.profile.owner_user_id,
            )
        elif isinstance(values, MedicationCandidate):
            if values.active_status in {None, "unknown"}:
                raise ApiError(
                    status_code=422,
                    code="CANDIDATE_REQUIRES_CORRECTION",
                    message="Confirm whether the medication is active before accepting it.",
                )
            target = Medication(
                profile_id=document.profile_id,
                name=values.name,
                dose=values.dose,
                dose_unit=values.dose_unit,
                frequency=values.frequency,
                route=values.route,
                start_date=values.start_date,
                end_date=values.end_date,
                is_active=values.active_status == "active",
                provenance=provenance,
                verification_status=verified,
            )
        elif isinstance(values, LabCandidate):
            target = Observation(
                profile_id=document.profile_id,
                display_name=values.test_name,
                value_number=values.value_number,
                value_text=values.value_text,
                unit=values.unit,
                reference_low=values.reference_low,
                reference_high=values.reference_high,
                interpretation=values.interpretation or values.reference_range_text,
                observed_at=self._required_observed_at(values.collected_date, document),
                provenance=provenance,
                verification_status=verified,
            )
        elif isinstance(values, SymptomCandidate):
            notes = values.notes
            if values.severity:
                notes = f"Reported severity: {values.severity}" + (f". {notes}" if notes else "")
            target = Symptom(
                profile_id=document.profile_id,
                name=values.name,
                severity=None,
                started_at=values.started_at,
                ended_at=values.ended_at,
                notes=notes,
                provenance=provenance,
                verification_status=verified,
            )
        else:
            target = Observation(
                profile_id=document.profile_id,
                display_name=values.measurement_name,
                value_number=values.value_number,
                value_text=values.value_text,
                unit=values.unit,
                interpretation=values.context,
                observed_at=self._required_observed_at(values.observed_at, document),
                provenance=provenance,
                verification_status=verified,
            )

        db.add(target)
        db.flush()
        link = EvidenceLink(
            source_document_id=document.id,
            page_number=values.page_number,
            source_excerpt=values.evidence_text,
        )
        if isinstance(target, HealthEvent):
            link.health_event_id = target.id
        elif isinstance(target, Observation):
            link.observation_id = target.id
        elif isinstance(target, Medication):
            link.medication_id = target.id
        else:
            link.symptom_id = target.id
        db.add(link)
        db.flush()
        return TrustedRecordReference(record_type=target.__tablename__, record_id=target.id)

    def _review(
        self,
        db: Session,
        candidate_id: str,
        *,
        correction: CandidateCorrectionRequest | None,
    ) -> CandidateReviewResult:
        candidate = self._require_candidate(db, candidate_id)
        self._reviewable(candidate)
        original_state = _safe_candidate_state(candidate)
        values = self._validated_candidate(candidate, correction)
        provenance = (
            ProvenanceType.USER_CORRECTED if correction is not None else ProvenanceType.AI_EXTRACTED
        )
        trusted = self._create_trusted(db, candidate, values, provenance)
        candidate.status = (
            CandidateStatus.CORRECTED if correction is not None else CandidateStatus.ACCEPTED
        )
        candidate.reviewed_by_user_id = candidate.document.profile.owner_user_id
        candidate.reviewed_at = utc_now()
        db.flush()
        after_state: dict[str, Any] = {
            "status": candidate.status.value,
            "provenance": provenance.value,
            "trusted_record": trusted.model_dump(),
        }
        if correction is not None:
            after_state["corrected_data"] = {
                key: value
                for key, value in values.model_dump(mode="json").items()
                if key != "evidence_text"
            }
        self.audit.append(
            db,
            action=("CANDIDATE_CORRECTED" if correction is not None else "CANDIDATE_ACCEPTED"),
            entity_type="extracted_candidate",
            entity_id=candidate.id,
            actor_user_id=candidate.reviewed_by_user_id,
            before_state=original_state,
            after_state=after_state,
        )
        db.commit()
        db.refresh(candidate)
        return CandidateReviewResult(candidate=self.detail(candidate), trusted_record=trusted)

    def accept(self, db: Session, candidate_id: str) -> CandidateReviewResult:
        return self._review(db, candidate_id, correction=None)

    def correct(
        self,
        db: Session,
        candidate_id: str,
        correction: CandidateCorrectionRequest,
    ) -> CandidateReviewResult:
        return self._review(db, candidate_id, correction=correction)

    def reject(self, db: Session, candidate_id: str) -> CandidateReviewResult:
        candidate = self._require_candidate(db, candidate_id)
        self._reviewable(candidate)
        before_state = _safe_candidate_state(candidate)
        candidate.status = CandidateStatus.REJECTED
        candidate.reviewed_by_user_id = candidate.document.profile.owner_user_id
        candidate.reviewed_at = utc_now()
        db.flush()
        self.audit.append(
            db,
            action="CANDIDATE_REJECTED",
            entity_type="extracted_candidate",
            entity_id=candidate.id,
            actor_user_id=candidate.reviewed_by_user_id,
            before_state=before_state,
            after_state={"status": CandidateStatus.REJECTED.value},
        )
        db.commit()
        db.refresh(candidate)
        return CandidateReviewResult(candidate=self.detail(candidate), trusted_record=None)


def get_extraction_service() -> ExtractionService:
    return ExtractionService(get_llm_provider())
