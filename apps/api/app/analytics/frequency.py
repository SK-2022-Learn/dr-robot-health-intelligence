"""Symptom report-frequency comparison without interpreting missing days as absence."""

from app.analytics.schemas import TrendClassification


def classify_frequency(
    recent_count: int,
    recent_days: int,
    baseline_count: int,
    baseline_days: int,
    stability_threshold_percent: float,
) -> tuple[TrendClassification, float | None, float | None, float | None]:
    if recent_count == 0 or baseline_count == 0:
        return TrendClassification.INSUFFICIENT_DATA, None, None, None
    recent_rate = recent_count / recent_days
    baseline_rate = baseline_count / baseline_days
    percent = ((recent_rate - baseline_rate) / baseline_rate) * 100
    if abs(percent) <= stability_threshold_percent:
        classification = TrendClassification.STABLE
    elif percent > 0:
        classification = TrendClassification.INCREASED
    else:
        classification = TrendClassification.DECREASED
    return classification, round(recent_rate, 4), round(baseline_rate, 4), round(percent, 4)
