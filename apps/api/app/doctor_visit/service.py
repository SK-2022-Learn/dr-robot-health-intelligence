"""Doctor Visit brief orchestration over trusted, profile-scoped services."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import Depends
from sqlalchemy.orm import Session

from app.analytics.schemas import TrendClassification, WhatChangedRequest
from app.analytics.service import AnalyticsService
from app.core.errors import ApiError
from app.database.enums import VerificationStatus
from app.database.models import HealthProfile
from app.doctor_visit.evidence import DoctorVisitEvidenceService, evidence_summary
from app.doctor_visit.questions import build_questions
from app.doctor_visit.renderer import rewrite_overview
from app.doctor_visit.schemas import (
    DoctorVisitBrief,
    RecentChangeItem,
    VisitMissingEvidenceItem,
)
from app.doctor_visit.sections import (
    current_medications,
    known_history,
    recent_observations,
    recent_symptoms,
)
from app.llm.base import LLMProvider
from app.llm.factory import get_llm_provider
from app.safety.service import SafetyService
from app.services.audit import AuditService
from app.timeline.missing_evidence import MissingEvidenceService
from app.timeline.schemas import TimelineEntityType
from app.timeline.service import TimelineService

SUMMARY_VERSION = "doctor-visit-v1"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class DoctorVisitService:
    def __init__(
        self,
        llm: LLMProvider,
        *,
        timeline: TimelineService | None = None,
        analytics: AnalyticsService | None = None,
        evidence: DoctorVisitEvidenceService | None = None,
        missing_evidence: MissingEvidenceService | None = None,
        safety: SafetyService | None = None,
        audit: AuditService | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.llm = llm
        self.timeline = timeline or TimelineService()
        self.analytics = analytics or AnalyticsService(llm)
        self.evidence = evidence or DoctorVisitEvidenceService()
        self.missing_evidence = missing_evidence or MissingEvidenceService(self.timeline)
        self.audit = audit or AuditService()
        self.safety = safety or SafetyService(self.audit)
        self.clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _profile(db: Session, profile_id: str) -> HealthProfile:
        profile = db.get(HealthProfile, profile_id)
        if profile is None:
            raise ApiError(
                status_code=404,
                code="PROFILE_NOT_FOUND",
                message="Health profile was not found.",
            )
        return profile

    @staticmethod
    def _age(date_of_birth: date | None, on_date: date) -> int | None:
        if date_of_birth is None:
            return None
        return (
            on_date.year
            - date_of_birth.year
            - ((on_date.month, on_date.day) < (date_of_birth.month, date_of_birth.day))
        )

    def generate(
        self,
        db: Session,
        profile_id: str,
        *,
        recent_days: int = 30,
        max_labs: int = 5,
        max_measurements: int = 8,
        max_symptoms: int = 5,
        include_llm_rewrite: bool = False,
    ) -> DoctorVisitBrief:
        profile = self._profile(db, profile_id)
        generated_at = _aware(self.clock())
        timeline = self.timeline.list(db, profile_id, sort="desc", limit=10_000)
        verified = [
            item
            for item in timeline.items
            if item.verification_status == VerificationStatus.VERIFIED
        ]

        history = known_history(db, profile_id, verified, self.evidence)
        medications = current_medications(db, profile_id, verified, self.evidence)
        labs, measurements = recent_observations(
            db,
            profile_id,
            verified,
            self.evidence,
            reference_date=generated_at.date(),
            recent_days=recent_days,
            max_labs=max_labs,
            max_measurements=max_measurements,
        )
        symptoms = recent_symptoms(
            db,
            profile_id,
            verified,
            self.evidence,
            reference_date=generated_at.date(),
            recent_days=recent_days,
            max_symptoms=max_symptoms,
        )

        analytics = self.analytics.what_changed(
            db,
            profile_id,
            WhatChangedRequest(
                reference_date=generated_at.date(),
                recent_days=recent_days,
                include_explanation=False,
            ),
        )
        changes = [
            RecentChangeItem(
                key=f"{result.metric.value}:{result.context.value if result.context else 'all'}",
                statement=result.explanation,
                analysis=result,
            )
            for result in analytics.results
            if result.classification != TrendClassification.INSUFFICIENT_DATA
        ][:5]

        trusted_ids = {item.entity_id for item in verified}
        structural = self.missing_evidence.list(db, profile_id)
        missing = [
            VisitMissingEvidenceItem(
                type=gap.type.value,
                message=gap.message,
                entity_type=gap.entity_type,
                entity_id=gap.entity_id,
            )
            for gap in structural.gaps
            if gap.entity_id in trusted_ids and gap.type.value != "UNVERIFIED_FACT"
        ]
        for medication in medications:
            missing.append(
                VisitMissingEvidenceItem(
                    type="STALE_MEDICATION_REVIEW",
                    message=(
                        "Medication reconciliation date is unavailable; "
                        "reconciliation may be needed."
                    ),
                    entity_type=TimelineEntityType.MEDICATION,
                    entity_id=medication.record_id,
                )
            )
        has_thyroid_history = any("thyroid" in item.title.casefold() for item in history)
        has_recent_thyroid_lab = any(
            item.name.casefold().strip() in {"tsh", "t3", "t4", "thyroid stimulating hormone"}
            or "thyroid" in item.name.casefold()
            for item in labs
        )
        if has_thyroid_history and not has_recent_thyroid_lab:
            missing.append(
                VisitMissingEvidenceItem(
                    type="MISSING_RECENT_THYROID_LAB",
                    message="No recent thyroid lab is recorded for this profile.",
                )
            )

        questions = build_questions(changes, missing)
        facts = {
            "history_count": len(history),
            "medication_count": len(medications),
            "lab_count": len(labs),
            "change_count": len(changes),
        }
        rewrite = rewrite_overview(
            self.llm,
            self.safety,
            facts,
            enabled=include_llm_rewrite,
            profile_id=profile_id,
        )
        audit_id = str(uuid4())
        if rewrite.safety is not None:
            self.safety.audit_result(
                db,
                rewrite.safety,
                entity_id=audit_id,
                profile_id=profile_id,
                actor_user_id=profile.owner_user_id,
            )

        cutoff_candidates = [_aware(item.occurred_at or item.created_at) for item in verified]
        if medications:
            cutoff_candidates.extend(_aware(item.last_updated_at) for item in medications)
        data_cutoff = max(cutoff_candidates, default=generated_at)
        summary = evidence_summary(timeline.items, len(missing))
        self.audit.append(
            db,
            action="DOCTOR_VISIT_BRIEF_GENERATED",
            entity_type="doctor_visit_brief",
            entity_id=audit_id,
            actor_user_id=profile.owner_user_id,
            after_state={
                "profile_id": profile_id,
                "summary_version": SUMMARY_VERSION,
                "generated_at": generated_at.isoformat(),
                "known_history_count": len(history),
                "recent_change_count": len(changes),
                "medication_count": len(medications),
                "recent_lab_count": len(labs),
                "recent_measurement_count": len(measurements),
                "recent_symptom_count": len(symptoms),
                "missing_evidence_count": len(missing),
                "rewrite_status": rewrite.status.value,
            },
        )
        db.commit()
        return DoctorVisitBrief(
            profile_id=profile_id,
            profile_display_name=profile.display_name,
            profile_age=self._age(profile.date_of_birth, generated_at.date()),
            date_of_birth=profile.date_of_birth,
            relationship_to_owner=profile.relationship_to_owner.value,
            generated_at=generated_at,
            data_cutoff=data_cutoff,
            summary_version=SUMMARY_VERSION,
            overview=rewrite.overview,
            overview_source=rewrite.source,
            rewrite_status=rewrite.status,
            known_history=history,
            recent_changes=changes,
            medications=medications,
            recent_labs=labs,
            recent_measurements=measurements,
            recent_symptoms=symptoms,
            missing_evidence=missing,
            questions_to_discuss=questions,
            evidence_summary=summary,
            safety_notes=[
                (
                    "This brief summarizes trusted records for discussion with a "
                    "healthcare professional."
                ),
                "It does not diagnose, prescribe, or recommend medication changes.",
                "Missing information means it is not recorded here; absence is not assumed.",
            ],
        )


def get_doctor_visit_service(
    llm: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> DoctorVisitService:
    return DoctorVisitService(llm)
