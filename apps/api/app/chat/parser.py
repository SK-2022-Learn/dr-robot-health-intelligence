"""Validate LLM output and reconcile narrowly supported explicit facts."""

import re

from pydantic import ValidationError

from app.chat.schemas import (
    ActivityEntry,
    BloodPressureEntry,
    DailyHealthExtraction,
    DailySymptomEntry,
    GlucoseContext,
    GlucoseEntry,
    SleepEntry,
    SymptomSeverity,
    WeightEntry,
)
from app.llm.types import LLMResponseError


def parse_daily_health_extraction(raw_response: str) -> DailyHealthExtraction:
    try:
        return DailyHealthExtraction.model_validate_json(raw_response)
    except ValidationError as error:
        raise LLMResponseError("Daily health extraction failed schema validation.") from error


def _duration_minutes(value: str, unit: str) -> int:
    number = float(value)
    return round(number * 60) if unit.startswith("hour") else round(number)


def _glucose_context(sentence: str) -> GlucoseContext:
    if "fasting" in sentence or "before food" in sentence:
        return GlucoseContext.FASTING
    if re.search(r"\bbefore\s+(a\s+)?(meal|breakfast|lunch|dinner)\b", sentence):
        return GlucoseContext.BEFORE_MEAL
    if re.search(r"\bafter\s+(a\s+)?(meal|breakfast|lunch|dinner|food)\b", sentence):
        return GlucoseContext.AFTER_MEAL
    if "random" in sentence:
        return GlucoseContext.RANDOM
    return GlucoseContext.UNKNOWN


def _rule_based_explicit_facts(content: str) -> DailyHealthExtraction:
    result = DailyHealthExtraction()
    sentences = [item.strip() for item in re.split(r"[.!?]+", content) if item.strip()]
    for original in sentences:
        sentence = original.casefold()
        glucose_match = re.search(
            r"\b(?:sugar|glucose)\s*(?:is|was|:)?\s*(\d+(?:\.\d+)?)"
            r"(?:\s*(mg/dl|mmol/l))?\b",
            sentence,
        )
        if glucose_match is None and any(
            isinstance(item, GlucoseEntry) for item in result.observations
        ):
            glucose_match = re.search(
                r"\b(?:before|after)\s+(?:a\s+)?(?:meal|breakfast|lunch|dinner|food)\s*"
                r"(?:was|is|:)?\s*(\d+(?:\.\d+)?)"
                r"(?:\s*(mg/dl|mmol/l))?\b",
                sentence,
            )
        if glucose_match:
            unit = "mmol/L" if glucose_match.group(2) == "mmol/l" else "mg/dL"
            result.observations.append(
                GlucoseEntry(
                    entry_type="glucose",
                    value=float(glucose_match.group(1)),
                    unit=unit,
                    context=_glucose_context(sentence),
                    confidence=0.99,
                )
            )

        pressure_match = re.search(
            r"\b(?:bp|blood\s+pressure)\s*(?:is|was|:)?\s*(\d{2,3})\s*/\s*(\d{2,3})\b",
            sentence,
        )
        if pressure_match:
            result.observations.append(
                BloodPressureEntry(
                    entry_type="blood_pressure",
                    systolic=int(pressure_match.group(1)),
                    diastolic=int(pressure_match.group(2)),
                    confidence=0.99,
                )
            )

        weight_match = re.search(
            r"\bweight\s*(?:is|was|:)?\s*(\d+(?:\.\d+)?)\s*(kg|kgs|kilograms?|lb|lbs|pounds?)?\b",
            sentence,
        )
        if weight_match:
            raw_unit = weight_match.group(2)
            unit = None
            if raw_unit in {"kg", "kgs", "kilogram", "kilograms"}:
                unit = "kg"
            elif raw_unit in {"lb", "lbs", "pound", "pounds"}:
                unit = "lb"
            result.observations.append(
                WeightEntry(
                    entry_type="weight",
                    value=float(weight_match.group(1)),
                    unit=unit,
                    confidence=0.99,
                )
            )

        sleep_match = re.search(
            r"\b(?:slept|sleep)\s*(?:for\s*)?(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?)\b",
            sentence,
        )
        if sleep_match:
            result.sleep_entries.append(
                SleepEntry(
                    duration_minutes=_duration_minutes(sleep_match.group(1), sleep_match.group(2)),
                    confidence=0.99,
                )
            )

        activity_match = re.search(
            r"\b(walked|walking|ran|running|cycled|cycling|exercised|exercise)\s*(?:for\s*)?"
            r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?)\b",
            sentence,
        )
        if activity_match:
            activity_names = {
                "walked": "walking",
                "walking": "walking",
                "ran": "running",
                "running": "running",
                "cycled": "cycling",
                "cycling": "cycling",
                "exercised": "exercise",
                "exercise": "exercise",
            }
            result.activities.append(
                ActivityEntry(
                    activity_type=activity_names[activity_match.group(1)],
                    duration_minutes=_duration_minutes(
                        activity_match.group(2), activity_match.group(3)
                    ),
                    confidence=0.99,
                )
            )

        for symptom_name in (
            "constipation",
            "headache",
            "nausea",
            "dizziness",
            "fatigue",
        ):
            if re.search(rf"\b{symptom_name}\b", sentence):
                if re.search(r"\b(little|mild)\b", sentence):
                    severity = SymptomSeverity.MILD
                elif "moderate" in sentence:
                    severity = SymptomSeverity.MODERATE
                elif "severe" in sentence:
                    severity = SymptomSeverity.SEVERE
                else:
                    severity = SymptomSeverity.UNKNOWN
                result.symptoms.append(
                    DailySymptomEntry(
                        name=symptom_name.capitalize(),
                        severity=severity,
                        confidence=0.99,
                    )
                )
    return result


def _observation_key(item: GlucoseEntry | BloodPressureEntry | WeightEntry) -> tuple:
    if isinstance(item, GlucoseEntry):
        return ("glucose", item.value)
    if isinstance(item, BloodPressureEntry):
        return ("blood_pressure", item.systolic, item.diastolic)
    return ("weight", item.value)


def supplement_explicit_facts(
    extraction: DailyHealthExtraction, content: str
) -> DailyHealthExtraction:
    """Ground supported model output in explicit text and restore model omissions."""

    explicit = _rule_based_explicit_facts(content)
    model_observations = {_observation_key(item): item for item in extraction.observations}
    for item in explicit.observations:
        key = _observation_key(item)
        existing = model_observations.get(key)
        if existing is not None:
            if isinstance(item, GlucoseEntry) and isinstance(existing, GlucoseEntry):
                item.observed_at = existing.observed_at
            elif isinstance(item, BloodPressureEntry) and isinstance(existing, BloodPressureEntry):
                item.observed_at = existing.observed_at
            elif isinstance(item, WeightEntry) and isinstance(existing, WeightEntry):
                item.observed_at = existing.observed_at
    extraction.observations = explicit.observations

    model_sleep = {item.duration_minutes: item for item in extraction.sleep_entries}
    for item in explicit.sleep_entries:
        existing = model_sleep.get(item.duration_minutes)
        if existing is not None:
            item.sleep_date = existing.sleep_date
            if existing.quality and existing.quality.casefold() in content.casefold():
                item.quality = existing.quality
    extraction.sleep_entries = explicit.sleep_entries

    model_activities = {
        (item.activity_type.casefold(), item.duration_minutes, item.distance): item
        for item in extraction.activities
    }
    for item in explicit.activities:
        existing = model_activities.get(
            (item.activity_type.casefold(), item.duration_minutes, item.distance)
        )
        if existing is not None:
            item.observed_at = existing.observed_at
    extraction.activities = explicit.activities

    content_folded = content.casefold()
    explicit_symptoms = {item.name.casefold(): item for item in explicit.symptoms}
    for item in extraction.symptoms:
        grounded = explicit_symptoms.get(item.name.casefold())
        if grounded is not None:
            grounded.started_at = item.started_at
            if item.duration_text and item.duration_text.casefold() in content_folded:
                grounded.duration_text = item.duration_text
            if item.notes and item.notes.casefold() in content_folded:
                grounded.notes = item.notes
    for item in extraction.symptoms:
        name = item.name.casefold()
        if name not in content_folded or name in explicit_symptoms:
            continue
        item.severity = SymptomSeverity.UNKNOWN
        for severity in (
            SymptomSeverity.MILD,
            SymptomSeverity.MODERATE,
            SymptomSeverity.SEVERE,
        ):
            if severity.value.casefold() in content_folded:
                item.severity = severity
                break
        if item.duration_text and item.duration_text.casefold() not in content_folded:
            item.duration_text = None
        if item.notes and item.notes.casefold() not in content_folded:
            item.notes = None
        explicit_symptoms[name] = item
    extraction.symptoms = list(explicit_symptoms.values())
    return extraction
