"""Context, diagnosis, logging, and generic post-response rules."""

import re

from app.safety.enums import SafetyCategory, SafetyDecision
from app.safety.policy import DIAGNOSIS_RESPONSE, UNSAFE_DRAFT_RESPONSE, RuleMatch

_PAST_MARKER = re.compile(
    r"\b(?:19|20)\d{2}\b|\b(?:last\s+year|years?\s+ago|previously|in\s+the\s+past)\b",
    re.IGNORECASE,
)
_HISTORICAL_REPORT = re.compile(
    r"\b(?:i\s+had|my\s+doctor\s+told\s+me|i\s+was\s+told)\b",
    re.IGNORECASE,
)
_RESOLUTION = re.compile(r"\b(?:resolved|went\s+away|no\s+longer|last\s+year)\b", re.I)
_CURRENT_MARKER = re.compile(
    r"\b(?:now|right\s+now|currently|today|tonight|still|ongoing|at\s+the\s+moment)\b",
    re.IGNORECASE,
)
_CURRENT_REQUEST = re.compile(r"\b(?:should|can|could|may|do)\s+i\b", re.IGNORECASE)
_DIAGNOSIS_REQUEST = re.compile(
    r"\bdo\s+i\s+have\b|\bis\s+this\s+(?:cancer|diabetes|a\s+disease|an?\s+infection)\b|"
    r"\bdiagnos(?:e\s+me|is)\b|\bdoes\s+this\s+mean\s+i\s+have\b",
    re.IGNORECASE,
)
_DRAFT_DIAGNOSIS = re.compile(
    r"\b(?:you\s+(?:definitely\s+|certainly\s+)?have|your\s+diagnosis\s+is|this\s+is)\b"
    r".{0,35}\b(?:diabetes|cancer|stroke|infection|thyroid\s+disease)\b",
    re.IGNORECASE,
)
_LOG_ENTRY = re.compile(
    r"\b(?:fasting|glucose|sugar|blood\s+pressure|bp|weight|slept|walked|symptom)\b"
    r".{0,35}\b\d+(?:\.\d+)?\b",
    re.IGNORECASE,
)


def is_historical_report(text: str) -> bool:
    return bool(
        _HISTORICAL_REPORT.search(text)
        and (_PAST_MARKER.search(text) or _RESOLUTION.search(text))
        and not _CURRENT_MARKER.search(text)
        and not _CURRENT_REQUEST.search(text)
    )


def match_diagnosis_pre(text: str) -> RuleMatch | None:
    if not _DIAGNOSIS_REQUEST.search(text):
        return None
    return RuleMatch(
        SafetyDecision.WARN,
        SafetyCategory.DIAGNOSIS_REQUEST,
        "SAFE-DIAG-001",
        "An autonomous diagnosis is not provided.",
        DIAGNOSIS_RESPONSE,
        professional=True,
    )


def match_diagnosis_post(draft: str) -> RuleMatch | None:
    if not _DRAFT_DIAGNOSIS.search(draft):
        return None
    return RuleMatch(
        SafetyDecision.BLOCK,
        SafetyCategory.DIAGNOSIS_REQUEST,
        "SAFE-DIAG-POST-001",
        "Diagnostic certainty was removed from the response.",
        UNSAFE_DRAFT_RESPONSE,
        professional=True,
    )


def is_logging(text: str) -> bool:
    return bool(_LOG_ENTRY.search(text) or is_historical_report(text))
