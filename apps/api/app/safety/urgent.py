"""Conservative red-flag rules that escalate without diagnosing."""

import re

from app.safety.enums import SafetyCategory, SafetyDecision
from app.safety.policy import SELF_HARM_RESPONSE, URGENT_RESPONSE, RuleMatch

_CURRENT_REPORT = re.compile(
    r"\b(i\s+(?:have|am|feel|lost|cannot|can't)|i'm|my\s+(?:face|arm|throat)|"
    r"experiencing|right\s+now|currently)\b",
    re.IGNORECASE,
)
_RED_FLAGS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("SAFE-URGENT-001", re.compile(r"\b(?:severe|crushing)\s+chest\s+pain\b", re.I)),
    (
        "SAFE-URGENT-002",
        re.compile(r"\b(?:cannot|can't|difficulty|struggling\s+to)\s+breathe\b", re.I),
    ),
    (
        "SAFE-URGENT-003",
        re.compile(
            r"\bface\s+(?:is\s+)?droop(?:ing|ed)?\b|\b(?:cannot|can't)\s+move\s+(?:my\s+)?arm\b",
            re.I,
        ),
    ),
    (
        "SAFE-URGENT-004",
        re.compile(r"\b(?:bleeding\s+heavily|severe\s+(?:uncontrolled\s+)?bleeding)\b", re.I),
    ),
    ("SAFE-URGENT-005", re.compile(r"\b(?:lost|loss\s+of)\s+consciousness\b", re.I)),
    (
        "SAFE-URGENT-006",
        re.compile(r"\bseiz(?:ure|ing)\b.{0,35}\b(?:ongoing|won't\s+stop|cannot\s+stop)\b", re.I),
    ),
    (
        "SAFE-URGENT-007",
        re.compile(
            r"\b(?:throat|tongue|face)\s+(?:is\s+)?swelling\b|\bsevere\s+allergic\s+reaction\b",
            re.I,
        ),
    ),
)
_SELF_HARM = re.compile(
    r"\b(i\s+(?:want|plan|intend|am\s+going)\s+to\s+(?:kill|hurt|harm)\s+myself|"
    r"i\s+am\s+suicidal|suicidal\s+(?:thoughts|intent))\b",
    re.IGNORECASE,
)


def match_urgent(text: str) -> RuleMatch | None:
    if _SELF_HARM.search(text):
        return RuleMatch(
            SafetyDecision.ESCALATE,
            SafetyCategory.URGENT_SYMPTOM,
            "SAFE-URGENT-008",
            "Immediate crisis support is recommended.",
            SELF_HARM_RESPONSE,
            professional=True,
            emergency=True,
        )
    if not _CURRENT_REPORT.search(text):
        return None
    for rule_id, pattern in _RED_FLAGS:
        if pattern.search(text):
            return RuleMatch(
                SafetyDecision.ESCALATE,
                SafetyCategory.URGENT_SYMPTOM,
                rule_id,
                "Urgent professional evaluation is recommended.",
                URGENT_RESPONSE,
                professional=True,
                emergency=True,
            )
    return None
