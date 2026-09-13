"""Deterministic assembly of Doctor Visit brief sections."""

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Medication, Observation
from app.doctor_visit.evidence import DoctorVisitEvidenceService
from app.doctor_visit.schemas import (
    KnownHistoryItem,
    MedicationSummaryItem,
    ObservationSummaryItem,
    SymptomSummaryItem,
)
from app.timeline.schemas import TimelineEntityType, TimelineItem, TimelineType

LAB_NAMES = {
    "a1c",
    "creatinine",
    "fasting glucose",
    "glucose",
    "hba1c",
    "t3",
    "t4",
    "thyroid stimulating hormone",
    "tsh",
}


def known_history(
    db: Session,
    profile_id: str,
    items: list[TimelineItem],
    evidence: DoctorVisitEvidenceService,
) -> list[KnownHistoryItem]:
    included = {
        TimelineType.CONDITION,
        TimelineType.PROCEDURE,
        TimelineType.HOSPITALIZATION,
    }
    rows = [item for item in items if item.timeline_type in included]
    rows.sort(key=lambda item: (item.occurred_at or datetime.max, item.title.casefold()))
    return [
        KnownHistoryItem(
            record_id=item.entity_id,
            title=item.title,
            timeline_type=item.timeline_type,
            documented_date=item.occurred_at,
            end_date=item.end_at,
            evidence=evidence.reference(db, profile_id, item),
        )
        for item in rows
    ]


def current_medications(
    db: Session,
    profile_id: str,
    items: list[TimelineItem],
    evidence: DoctorVisitEvidenceService,
) -> list[MedicationSummaryItem]:
    timeline_by_id = {
        item.entity_id: item for item in items if item.entity_type == TimelineEntityType.MEDICATION
    }
    if not timeline_by_id:
        return []
    rows = db.scalars(
        select(Medication).where(
            Medication.profile_id == profile_id,
            Medication.id.in_(timeline_by_id),
            Medication.is_active.is_(True),
        )
    ).all()
    rows = sorted(rows, key=lambda row: (row.name.casefold(), row.id))
    return [
        MedicationSummaryItem(
            record_id=row.id,
            name=row.name,
            dose=row.dose,
            dose_unit=row.dose_unit,
            frequency=row.frequency,
            route=row.route,
            start_date=row.start_date,
            end_date=row.end_date,
            last_updated_at=row.updated_at,
            reconciliation_needed=True,
            evidence=evidence.reference(db, profile_id, timeline_by_id[row.id]),
        )
        for row in rows
    ]


def recent_observations(
    db: Session,
    profile_id: str,
    items: list[TimelineItem],
    evidence: DoctorVisitEvidenceService,
    *,
    reference_date: date,
    recent_days: int,
    max_labs: int,
    max_measurements: int,
) -> tuple[list[ObservationSummaryItem], list[ObservationSummaryItem]]:
    cutoff = reference_date - timedelta(days=recent_days - 1)
    timeline_by_id = {
        item.entity_id: item
        for item in items
        if item.entity_type == TimelineEntityType.OBSERVATION
        and item.occurred_at is not None
        and cutoff <= item.occurred_at.date() <= reference_date
    }
    if not timeline_by_id:
        return [], []
    rows = list(
        db.scalars(
            select(Observation)
            .where(
                Observation.profile_id == profile_id,
                Observation.id.in_(timeline_by_id),
            )
            .order_by(Observation.observed_at.desc(), Observation.id)
        )
    )

    def summary(row: Observation) -> ObservationSummaryItem:
        raw = row.value_number if row.value_number is not None else row.value_text
        value = f"{raw:g}" if isinstance(raw, float) else str(raw)
        return ObservationSummaryItem(
            record_id=row.id,
            name=row.display_name,
            value=value,
            unit=row.unit,
            observed_at=row.observed_at,
            interpretation=row.interpretation,
            evidence=evidence.reference(db, profile_id, timeline_by_id[row.id]),
        )

    labs = [row for row in rows if row.display_name.casefold().strip() in LAB_NAMES]
    measurements = [row for row in rows if row.display_name.casefold().strip() not in LAB_NAMES]
    return [summary(row) for row in labs[:max_labs]], [
        summary(row) for row in measurements[:max_measurements]
    ]


def recent_symptoms(
    db: Session,
    profile_id: str,
    items: list[TimelineItem],
    evidence: DoctorVisitEvidenceService,
    *,
    reference_date: date,
    recent_days: int,
    max_symptoms: int,
) -> list[SymptomSummaryItem]:
    cutoff = reference_date - timedelta(days=recent_days - 1)
    grouped: dict[str, list[TimelineItem]] = defaultdict(list)
    labels: dict[str, str] = {}
    for item in items:
        if (
            item.entity_type == TimelineEntityType.SYMPTOM
            and item.occurred_at is not None
            and cutoff <= item.occurred_at.date() <= reference_date
        ):
            key = item.title.casefold().strip()
            grouped[key].append(item)
            labels[key] = item.title
    ordered = sorted(
        grouped,
        key=lambda key: max(item.occurred_at for item in grouped[key] if item.occurred_at),
        reverse=True,
    )[:max_symptoms]
    result: list[SymptomSummaryItem] = []
    for key in ordered:
        rows = sorted(grouped[key], key=lambda item: item.occurred_at or datetime.min, reverse=True)
        count = len(rows)
        result.append(
            SymptomSummaryItem(
                name=labels[key],
                report_count=count,
                most_recent=rows[0].occurred_at,
                statement=(
                    f"{labels[key]} was reported {count} time(s) in the recent "
                    f"{recent_days}-day period."
                ),
                evidence=[evidence.reference(db, profile_id, item) for item in rows],
            )
        )
    return result
