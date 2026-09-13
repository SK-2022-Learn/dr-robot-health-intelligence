"""Deterministic-first intent routing; no model is required for known workflows."""

import re

from app.agents.schemas import AgentIntent

_DAILY_VALUE = re.compile(
    r"\b(?:sugar|glucose|fasting|blood\s*pressure|bp|weight|slept|walked|symptom)\b"
    r".{0,45}\b\d+(?:\.\d+)?\b",
    re.I,
)
_UNSAFE_ACTION = re.compile(
    r"\b(?:should|can|could|may|do)\s+i\b.{0,70}\b(?:stop|start|double|increase|"
    r"decrease|skip|switch|replace|take)\b",
    re.I,
)


def route_intent(query: str) -> AgentIntent:
    """Classify stable product intents with transparent lexical rules."""

    text = " ".join(query.casefold().split())
    if _UNSAFE_ACTION.search(text):
        return AgentIntent.UNSUPPORTED_MEDICAL_ACTION
    if _DAILY_VALUE.search(text):
        return AgentIntent.DAILY_LOG
    if any(term in text for term in ("doctor visit", "visit summary", "appointment brief")):
        return AgentIntent.DOCTOR_VISIT
    if any(term in text for term in ("family", "relatives", "runs in my")) and any(
        term in text for term in ("repeat", "pattern", "condition", "history", "shared")
    ):
        return AgentIntent.FAMILY_QUERY
    if any(
        term in text for term in ("why do you say", "show the source", "source for", "evidence")
    ):
        return AgentIntent.EVIDENCE_QUERY
    if any(
        term in text
        for term in ("what changed", "trend", "baseline", "compared with", "since june")
    ):
        return AgentIntent.ANALYTICS_QUERY
    if any(term in text for term in ("when was", "first documented", "timeline", "history of")):
        return AgentIntent.TIMELINE_QUERY
    if any(
        term in text for term in ("latest", "my record", "my medication", "recorded", "do i have")
    ):
        return AgentIntent.RECORD_LOOKUP
    if text.startswith(("what is ", "what does ", "how does ", "explain ")):
        return AgentIntent.GENERAL_HEALTH_INFORMATION
    return AgentIntent.UNKNOWN
