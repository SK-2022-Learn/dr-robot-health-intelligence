"""Deterministic data-confidence rules; these are not clinical confidence."""

from datetime import date

from app.analytics.numeric import NormalizedPoint
from app.analytics.schemas import DataConfidence, TrendClassification


def _coverage(points: list[NormalizedPoint], window_days: int) -> float:
    if len(points) < 2:
        return 0.0
    dates = [point.observation.observed_at.date() for point in points]
    return min(1.0, ((max(dates) - min(dates)).days + 1) / window_days)


def numeric_confidence(
    recent: list[NormalizedPoint],
    baseline: list[NormalizedPoint],
    classification: TrendClassification,
    recent_days: int,
    baseline_days: int,
    skipped_values: int,
) -> tuple[DataConfidence, str]:
    if classification == TrendClassification.INSUFFICIENT_DATA:
        return DataConfidence.INSUFFICIENT, "Minimum sample counts were not met."
    recent_coverage = _coverage(recent, recent_days)
    baseline_coverage = _coverage(baseline, baseline_days)
    if (
        len(recent) >= 5
        and len(baseline) >= 5
        and recent_coverage >= 0.5
        and baseline_coverage >= 0.5
        and skipped_values == 0
    ):
        return DataConfidence.HIGH, "At least five verified readings span half of both windows."
    if len(recent) >= 3 and len(baseline) >= 3 and skipped_values <= 1:
        return (
            DataConfidence.MODERATE,
            "At least three verified readings are available in both windows.",
        )
    return (
        DataConfidence.LOW,
        "Minimum counts are met, but sample size or time coverage is limited.",
    )


def frequency_confidence(
    recent_count: int,
    baseline_count: int,
    classification: TrendClassification,
) -> tuple[DataConfidence, str]:
    if classification == TrendClassification.INSUFFICIENT_DATA:
        return DataConfidence.INSUFFICIENT, (
            "A missing period is unknown, so symptom absence was not assumed."
        )
    if recent_count >= 5 and baseline_count >= 5:
        return DataConfidence.HIGH, "At least five verified reports are present in both periods."
    if recent_count >= 3 and baseline_count >= 3:
        return (
            DataConfidence.MODERATE,
            "At least three verified reports are present in both periods.",
        )
    return DataConfidence.LOW, "Both periods contain reports, but the sample size is limited."


def days_inclusive(start: date, end: date) -> int:
    return (end - start).days + 1
