"""Profile-scoped orchestration for deterministic personal-baseline analytics."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.baseline import select_periods
from app.analytics.confidence import frequency_confidence, numeric_confidence
from app.analytics.explanation import explain_result
from app.analytics.frequency import classify_frequency
from app.analytics.numeric import (
    METRIC_LABELS,
    METRIC_UNITS,
    NormalizedPoint,
    classify_numeric,
    glucose_context,
    normalize_observation,
    observation_metrics,
    summarize,
)
from app.analytics.rules import FREQUENCY_CALCULATION_VERSION, NUMERIC_CALCULATION_VERSION
from app.analytics.schemas import (
    AnalyticsEvidence,
    AnalyticsMetric,
    AvailableMetric,
    AvailableMetricsResponse,
    DataConfidence,
    GlucoseContext,
    SymptomEvidence,
    SymptomFrequencyResult,
    TrendAnalysisResult,
    TrendClassification,
    WhatChangedRequest,
    WhatChangedResponse,
)
from app.config import Settings, get_settings
from app.core.errors import ApiError
from app.database.enums import VerificationStatus
from app.database.models import HealthProfile, Observation, Symptom
from app.llm.base import LLMProvider
from app.repositories.observation import ObservationRepository
from app.timeline.evidence import EvidenceService
from app.timeline.schemas import ChatEvidenceSource, DocumentEvidenceSource, TimelineEntityType


class AnalyticsService:
    def __init__(
        self,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
        observations: ObservationRepository | None = None,
        evidence: EvidenceService | None = None,
    ) -> None:
        self.llm = llm
        self.settings = settings or get_settings()
        self.observations = observations or ObservationRepository()
        self.evidence = evidence or EvidenceService()

    @staticmethod
    def _require_profile(db: Session, profile_id: str) -> None:
        if db.get(HealthProfile, profile_id) is None:
            raise ApiError(
                status_code=404,
                code="PROFILE_NOT_FOUND",
                message="Health profile was not found.",
            )

    @staticmethod
    def _validate_context(metric: AnalyticsMetric, context: GlucoseContext | None) -> None:
        if context is not None and metric != AnalyticsMetric.GLUCOSE:
            raise ApiError(
                status_code=400,
                code="INVALID_ANALYTICS_CONTEXT",
                message="A meal context can only be used with glucose analytics.",
            )

    @staticmethod
    def _original_value(observation: Observation) -> str:
        value: object = (
            observation.value_number
            if observation.value_number is not None
            else observation.value_text
        )
        rendered = f"{value:g}" if isinstance(value, float) else str(value)
        return f"{rendered} {observation.unit}".strip() if observation.unit else rendered

    def _evidence_point(
        self,
        db: Session,
        profile_id: str,
        point: NormalizedPoint,
    ) -> AnalyticsEvidence:
        resolved = self.evidence.resolve(
            db,
            profile_id,
            TimelineEntityType.OBSERVATION,
            point.observation.id,
        )
        source_label = "No linked source"
        source_excerpt = None
        view_source_path = None
        if isinstance(resolved.source, DocumentEvidenceSource):
            page = f", page {resolved.source.page_number}" if resolved.source.page_number else ""
            source_label = f"{resolved.source.filename}{page}"
            source_excerpt = resolved.source.excerpt
            view_source_path = resolved.source.view_source_path
        elif isinstance(resolved.source, ChatEvidenceSource):
            source_label = resolved.source.label
            source_excerpt = resolved.source.message
        return AnalyticsEvidence(
            observation_id=point.observation.id,
            recorded_at=point.observation.observed_at,
            original_value=self._original_value(point.observation),
            normalized_value=round(point.value, 4),
            normalized_unit=point.unit,
            provenance=point.observation.provenance,
            verification_status=point.observation.verification_status,
            source_type=resolved.source_type,
            source_label=source_label,
            source_excerpt=source_excerpt,
            view_source_path=view_source_path,
            evidence_path=(
                f"/api/v1/profiles/{profile_id}/evidence/observation/{point.observation.id}"
            ),
        )

    def trend(
        self,
        db: Session,
        profile_id: str,
        metric: AnalyticsMetric,
        *,
        context: GlucoseContext | None = None,
        reference_date: date | None = None,
        recent_days: int | None = None,
        baseline_days: int | None = None,
        include_explanation: bool = False,
    ) -> TrendAnalysisResult:
        self._require_profile(db, profile_id)
        self._validate_context(metric, context)
        reference = reference_date or date.today()
        recent_length = recent_days or self.settings.analytics_recent_window_days
        baseline_length = baseline_days or self.settings.analytics_baseline_window_days
        recent_period, baseline_period = select_periods(reference, recent_length, baseline_length)
        observations = self.observations.list_trusted_in_range(
            db, profile_id, baseline_period.start, recent_period.end
        )

        applicable = [row for row in observations if metric in observation_metrics(row)]
        if metric == AnalyticsMetric.GLUCOSE and context is not None:
            applicable = [row for row in applicable if glucose_context(row) == context]
        points = [
            normalized
            for row in applicable
            if (normalized := normalize_observation(row, metric)) is not None
        ]
        skipped_values = len(applicable) - len(points)
        recent = [
            point
            for point in points
            if recent_period.start <= point.observation.observed_at.date() <= recent_period.end
        ]
        baseline = [
            point
            for point in points
            if baseline_period.start <= point.observation.observed_at.date() <= baseline_period.end
        ]
        recent_summary = summarize(recent)
        baseline_summary = summarize(baseline)
        classification, absolute, percent = classify_numeric(
            recent_summary,
            baseline_summary,
            minimum_recent=self.settings.analytics_min_recent_numeric_points,
            minimum_baseline=self.settings.analytics_min_baseline_numeric_points,
            stability_threshold_percent=self.settings.analytics_stability_threshold_percent,
        )
        missing_data: list[str] = []
        if recent_summary.count < self.settings.analytics_min_recent_numeric_points:
            missing_data.append(
                f"Only {recent_summary.count} recent reading(s) are available; "
                f"at least {self.settings.analytics_min_recent_numeric_points} are required."
            )
        if baseline_summary.count < self.settings.analytics_min_baseline_numeric_points:
            missing_data.append(
                f"Only {baseline_summary.count} baseline reading(s) are available; "
                f"at least {self.settings.analytics_min_baseline_numeric_points} are required."
            )
        if skipped_values:
            missing_data.append(
                f"{skipped_values} record(s) had missing or unsupported numeric units "
                "and were excluded."
            )
        confidence, confidence_reason = numeric_confidence(
            recent,
            baseline,
            classification,
            recent_length,
            baseline_length,
            skipped_values,
        )
        used_points = baseline + recent
        evidence = [self._evidence_point(db, profile_id, point) for point in used_points]
        result_data = {
            "profile_id": profile_id,
            "metric": metric,
            "metric_label": METRIC_LABELS[metric],
            "context": context,
            "unit": METRIC_UNITS[metric],
            "reference_date": reference,
            "recent_period": recent_period,
            "baseline_period": baseline_period,
            "recent_count": recent_summary.count,
            "baseline_count": baseline_summary.count,
            "recent_summary": recent_summary,
            "baseline_summary": baseline_summary,
            "absolute_change": absolute,
            "percent_change": percent,
            "classification": classification,
            "confidence": confidence,
            "confidence_reason": confidence_reason,
            "missing_data": missing_data,
            "evidence_ids": [point.observation.id for point in used_points],
            "evidence": evidence,
            "calculation_version": NUMERIC_CALCULATION_VERSION,
            "stability_threshold_percent": self.settings.analytics_stability_threshold_percent,
        }
        explanation_data = {
            **result_data,
            "recent_summary": recent_summary.model_dump(),
            "baseline_summary": baseline_summary.model_dump(),
            "recent_period": recent_period.model_dump(),
            "baseline_period": baseline_period.model_dump(),
        }
        explanation, explanation_source = explain_result(
            self.llm, explanation_data, use_llm=include_explanation
        )
        return TrendAnalysisResult(
            **result_data,
            explanation=explanation,
            explanation_source=explanation_source,
        )

    def symptom_frequency(
        self,
        db: Session,
        profile_id: str,
        symptom_name: str,
        *,
        reference_date: date | None = None,
        recent_days: int | None = None,
        baseline_days: int | None = None,
    ) -> SymptomFrequencyResult:
        self._require_profile(db, profile_id)
        reference = reference_date or date.today()
        recent_length = recent_days or self.settings.analytics_recent_window_days
        baseline_length = baseline_days or self.settings.analytics_baseline_window_days
        recent_period, baseline_period = select_periods(reference, recent_length, baseline_length)
        rows = list(
            db.scalars(
                select(Symptom)
                .where(
                    Symptom.profile_id == profile_id,
                    Symptom.verification_status == VerificationStatus.VERIFIED,
                    Symptom.started_at.is_not(None),
                    Symptom.started_at >= baseline_period.start,
                    Symptom.started_at <= recent_period.end,
                )
                .order_by(Symptom.started_at, Symptom.id)
            )
        )
        matches = [row for row in rows if row.name.casefold() == symptom_name.casefold()]
        recent = [
            row
            for row in matches
            if row.started_at and recent_period.start <= row.started_at.date() <= recent_period.end
        ]
        baseline = [
            row
            for row in matches
            if row.started_at
            and baseline_period.start <= row.started_at.date() <= baseline_period.end
        ]
        classification, recent_rate, baseline_rate, percent = classify_frequency(
            len(recent),
            recent_length,
            len(baseline),
            baseline_length,
            self.settings.analytics_stability_threshold_percent,
        )
        confidence, confidence_reason = frequency_confidence(
            len(recent), len(baseline), classification
        )
        missing_data = []
        if not recent:
            missing_data.append("No recent report is recorded; symptom absence was not assumed.")
        if not baseline:
            missing_data.append("No baseline report is recorded; symptom absence was not assumed.")
        evidence_rows = baseline + recent
        evidence = [
            SymptomEvidence(
                symptom_id=row.id,
                recorded_at=row.started_at,
                severity=row.severity,
                provenance=row.provenance,
                verification_status=row.verification_status,
                evidence_path=f"/api/v1/profiles/{profile_id}/evidence/symptom/{row.id}",
            )
            for row in evidence_rows
            if row.started_at is not None
        ]
        if classification == TrendClassification.INSUFFICIENT_DATA:
            explanation = "Not enough recorded symptom data is available to compare both periods."
        else:
            direction = {
                TrendClassification.INCREASED: "more frequently",
                TrendClassification.DECREASED: "less frequently",
                TrendClassification.STABLE: "at a similar frequency",
            }[classification]
            explanation = f"{symptom_name} was reported {direction} in the recent period."
        return SymptomFrequencyResult(
            profile_id=profile_id,
            symptom_name=symptom_name,
            reference_date=reference,
            recent_period=recent_period,
            baseline_period=baseline_period,
            recent_count=len(recent),
            baseline_count=len(baseline),
            recent_rate_per_day=recent_rate,
            baseline_rate_per_day=baseline_rate,
            percent_change=percent,
            classification=classification,
            confidence=confidence,
            confidence_reason=confidence_reason,
            missing_data=missing_data,
            evidence_ids=[row.id for row in evidence_rows],
            evidence=evidence,
            calculation_version=FREQUENCY_CALCULATION_VERSION,
            explanation=explanation,
        )

    def available_metrics(self, db: Session, profile_id: str) -> AvailableMetricsResponse:
        self._require_profile(db, profile_id)
        rows = list(
            db.scalars(
                select(Observation).where(
                    Observation.profile_id == profile_id,
                    Observation.verification_status == VerificationStatus.VERIFIED,
                )
            )
        )
        found: dict[AnalyticsMetric, set[GlucoseContext]] = {}
        for row in rows:
            for metric in observation_metrics(row):
                if normalize_observation(row, metric) is None:
                    continue
                found.setdefault(metric, set())
                if metric == AnalyticsMetric.GLUCOSE and (context := glucose_context(row)):
                    found[metric].add(context)
        metrics = [
            AvailableMetric(
                metric=metric,
                label=METRIC_LABELS[metric],
                contexts=sorted(found[metric], key=str),
            )
            for metric in AnalyticsMetric
            if metric in found
        ]
        symptom_names = sorted(
            set(
                db.scalars(
                    select(Symptom.name).where(
                        Symptom.profile_id == profile_id,
                        Symptom.verification_status == VerificationStatus.VERIFIED,
                        Symptom.started_at.is_not(None),
                    )
                )
            ),
            key=str.casefold,
        )
        return AvailableMetricsResponse(
            profile_id=profile_id,
            metrics=metrics,
            symptoms=symptom_names,
        )

    def what_changed(
        self,
        db: Session,
        profile_id: str,
        request: WhatChangedRequest,
    ) -> WhatChangedResponse:
        reference = request.reference_date or date.today()
        recent_days = request.recent_days or self.settings.analytics_recent_window_days
        if request.since:
            recent_days = (reference - request.since).days + 1
            if not 1 <= recent_days <= 365:
                raise ApiError(
                    status_code=400,
                    code="INVALID_ANALYTICS_WINDOW",
                    message="The requested recent period must contain between 1 and 365 days.",
                )
        available = self.available_metrics(db, profile_id)
        requested: list[tuple[AnalyticsMetric, GlucoseContext | None]] = []
        for item in available.metrics:
            if item.metric == AnalyticsMetric.GLUCOSE and item.contexts:
                requested.extend((item.metric, context) for context in item.contexts)
            else:
                requested.append((item.metric, None))
        results = [
            self.trend(
                db,
                profile_id,
                metric,
                context=context,
                reference_date=reference,
                recent_days=recent_days,
                baseline_days=request.baseline_days or self.settings.analytics_baseline_window_days,
                include_explanation=request.include_explanation,
            )
            for metric, context in requested
        ]
        confidence_rank = {
            DataConfidence.HIGH: 3,
            DataConfidence.MODERATE: 2,
            DataConfidence.LOW: 1,
            DataConfidence.INSUFFICIENT: 0,
        }
        results.sort(
            key=lambda item: (
                item.classification != TrendClassification.INSUFFICIENT_DATA,
                confidence_rank[item.confidence],
                abs(item.percent_change or 0),
                max((point.recorded_at.isoformat() for point in item.evidence), default=""),
            ),
            reverse=True,
        )
        ranked = [
            item.model_copy(update={"display_priority": index})
            for index, item in enumerate(results, 1)
        ]
        return WhatChangedResponse(profile_id=profile_id, results=ranked)
