"""Pure numeric normalization, summaries, and non-clinical classification."""

import re
from dataclasses import dataclass
from statistics import fmean, median, pstdev

from app.analytics.schemas import (
    AnalyticsMetric,
    GlucoseContext,
    NumericSummary,
    TrendClassification,
)
from app.database.models import Observation

METRIC_LABELS = {
    AnalyticsMetric.GLUCOSE: "Glucose",
    AnalyticsMetric.HBA1C: "HbA1c",
    AnalyticsMetric.WEIGHT: "Weight",
    AnalyticsMetric.SYSTOLIC_BLOOD_PRESSURE: "Systolic blood pressure",
    AnalyticsMetric.DIASTOLIC_BLOOD_PRESSURE: "Diastolic blood pressure",
    AnalyticsMetric.SLEEP_DURATION: "Sleep duration",
    AnalyticsMetric.ACTIVITY_DURATION: "Activity duration per logged entry",
}

METRIC_UNITS = {
    AnalyticsMetric.GLUCOSE: "mg/dL",
    AnalyticsMetric.HBA1C: "%",
    AnalyticsMetric.WEIGHT: "kg",
    AnalyticsMetric.SYSTOLIC_BLOOD_PRESSURE: "mmHg",
    AnalyticsMetric.DIASTOLIC_BLOOD_PRESSURE: "mmHg",
    AnalyticsMetric.SLEEP_DURATION: "min",
    AnalyticsMetric.ACTIVITY_DURATION: "min",
}


@dataclass(frozen=True)
class NormalizedPoint:
    observation: Observation
    value: float
    unit: str


def _identity(observation: Observation) -> str:
    return " ".join((observation.code or "", observation.display_name)).lower()


def observation_metrics(observation: Observation) -> set[AnalyticsMetric]:
    identity = _identity(observation)
    if "blood pressure" in identity or "blood_pressure" in identity:
        return {
            AnalyticsMetric.SYSTOLIC_BLOOD_PRESSURE,
            AnalyticsMetric.DIASTOLIC_BLOOD_PRESSURE,
        }
    if "systolic" in identity:
        return {AnalyticsMetric.SYSTOLIC_BLOOD_PRESSURE}
    if "diastolic" in identity:
        return {AnalyticsMetric.DIASTOLIC_BLOOD_PRESSURE}
    if "hba1c" in identity or "a1c" in identity:
        return {AnalyticsMetric.HBA1C}
    if "glucose" in identity:
        return {AnalyticsMetric.GLUCOSE}
    if "weight" in identity:
        return {AnalyticsMetric.WEIGHT}
    if "sleep" in identity and "duration" in identity:
        return {AnalyticsMetric.SLEEP_DURATION}
    if "activity" in identity:
        return {AnalyticsMetric.ACTIVITY_DURATION}
    return set()


def glucose_context(observation: Observation) -> GlucoseContext | None:
    raw = " ".join(
        (observation.interpretation or "", observation.code or "", observation.display_name)
    ).upper()
    aliases = {
        GlucoseContext.AFTER_MEAL: ("AFTER_MEAL", "POST-MEAL", "POST MEAL", "POSTPRANDIAL"),
        GlucoseContext.BEFORE_MEAL: ("BEFORE_MEAL", "PRE-MEAL", "PRE MEAL", "PREPRANDIAL"),
        GlucoseContext.FASTING: ("FASTING",),
        GlucoseContext.RANDOM: ("RANDOM",),
    }
    return next(
        (context for context, values in aliases.items() if any(v in raw for v in values)), None
    )


def _duration_minutes(value: float, unit: str) -> float | None:
    normalized = unit.strip().lower()
    if normalized in {"min", "minute", "minutes"}:
        return value
    if normalized in {"h", "hr", "hrs", "hour", "hours"}:
        return value * 60
    return None


def normalize_observation(
    observation: Observation,
    metric: AnalyticsMetric,
) -> NormalizedPoint | None:
    if metric not in observation_metrics(observation):
        return None
    raw_unit = (observation.unit or "").strip()
    value = observation.value_number
    if metric in {
        AnalyticsMetric.SYSTOLIC_BLOOD_PRESSURE,
        AnalyticsMetric.DIASTOLIC_BLOOD_PRESSURE,
    }:
        if (
            value is not None
            and metric in observation_metrics(observation)
            and "blood pressure" not in _identity(observation)
        ):
            return NormalizedPoint(observation, float(value), "mmHg")
        match = re.fullmatch(
            r"\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*", observation.value_text or ""
        )
        if not match:
            return None
        position = 1 if metric == AnalyticsMetric.SYSTOLIC_BLOOD_PRESSURE else 2
        return NormalizedPoint(observation, float(match.group(position)), "mmHg")
    if value is None:
        return None
    if metric == AnalyticsMetric.WEIGHT:
        unit = raw_unit.lower()
        if unit in {"kg", "kilogram", "kilograms"}:
            normalized_value = float(value)
        elif unit in {"lb", "lbs", "pound", "pounds"}:
            normalized_value = float(value) * 0.45359237
        else:
            return None
        return NormalizedPoint(observation, normalized_value, "kg")
    if metric in {AnalyticsMetric.SLEEP_DURATION, AnalyticsMetric.ACTIVITY_DURATION}:
        normalized_value = _duration_minutes(float(value), raw_unit)
        return (
            NormalizedPoint(observation, normalized_value, "min")
            if normalized_value is not None
            else None
        )
    if metric == AnalyticsMetric.GLUCOSE:
        if raw_unit.lower() == "mmol/l":
            return NormalizedPoint(observation, float(value) * 18.0182, "mg/dL")
        if raw_unit.lower() not in {"mg/dl", "mg/dl."}:
            return None
        return NormalizedPoint(observation, float(value), "mg/dL")
    if metric == AnalyticsMetric.HBA1C:
        return NormalizedPoint(observation, float(value), "%") if raw_unit == "%" else None
    return None


def summarize(points: list[NormalizedPoint]) -> NumericSummary:
    values = [point.value for point in points]
    if not values:
        return NumericSummary(
            count=0,
            mean=None,
            median=None,
            minimum=None,
            maximum=None,
            standard_deviation=None,
            first_value=None,
            last_value=None,
        )
    return NumericSummary(
        count=len(values),
        mean=round(fmean(values), 4),
        median=round(float(median(values)), 4),
        minimum=round(min(values), 4),
        maximum=round(max(values), 4),
        standard_deviation=round(pstdev(values), 4) if len(values) > 1 else 0.0,
        first_value=round(values[0], 4),
        last_value=round(values[-1], 4),
    )


def classify_numeric(
    recent: NumericSummary,
    baseline: NumericSummary,
    *,
    minimum_recent: int,
    minimum_baseline: int,
    stability_threshold_percent: float,
) -> tuple[TrendClassification, float | None, float | None]:
    if recent.count < minimum_recent or baseline.count < minimum_baseline:
        return TrendClassification.INSUFFICIENT_DATA, None, None
    assert recent.mean is not None and baseline.mean is not None
    absolute = round(recent.mean - baseline.mean, 4)
    percent = None if baseline.mean == 0 else round((absolute / abs(baseline.mean)) * 100, 4)
    if percent is not None:
        if abs(percent) <= stability_threshold_percent:
            return TrendClassification.STABLE, absolute, percent
        classification = (
            TrendClassification.INCREASED if absolute > 0 else TrendClassification.DECREASED
        )
        return classification, absolute, percent
    if absolute == 0:
        return TrendClassification.STABLE, absolute, None
    return (
        TrendClassification.INCREASED if absolute > 0 else TrendClassification.DECREASED,
        absolute,
        None,
    )
