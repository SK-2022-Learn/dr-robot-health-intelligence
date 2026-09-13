"""Non-overlapping recent and personal-baseline window selection."""

from datetime import date, timedelta

from app.analytics.schemas import AnalysisPeriod


def select_periods(
    reference_date: date,
    recent_days: int,
    baseline_days: int,
) -> tuple[AnalysisPeriod, AnalysisPeriod]:
    """Return inclusive windows with baseline ending the day before recent starts."""

    recent_start = reference_date - timedelta(days=recent_days - 1)
    baseline_end = recent_start - timedelta(days=1)
    baseline_start = baseline_end - timedelta(days=baseline_days - 1)
    return (
        AnalysisPeriod(start=recent_start, end=reference_date, days=recent_days),
        AnalysisPeriod(start=baseline_start, end=baseline_end, days=baseline_days),
    )
