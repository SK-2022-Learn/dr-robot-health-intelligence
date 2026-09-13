"""Medication-change, prescribing, and risky self-treatment rules."""

import re

from app.safety.enums import SafetyCategory, SafetyDecision
from app.safety.policy import (
    HIGH_RISK_RESPONSE,
    MEDICATION_RESPONSE,
    PRESCRIBING_RESPONSE,
    REPLACEMENT_RESPONSE,
    UNSAFE_DRAFT_RESPONSE,
    RuleMatch,
)

_CHANGE_REQUEST = re.compile(
    r"\b(?:should|can|could|may|do)\s+i\b.{0,65}\b(?:stop|start|change|double|increase|"
    r"decrease|skip|reduce|switch|replace)\b|\b(?:can|should)\s+i\s+double\s+(?:my\s+)?dose\b",
    re.IGNORECASE,
)
_TREATMENT_REPLACEMENT = re.compile(
    r"\b(?:instead\s+of|replace|switch\s+from)\b.{0,60}\b(?:prescribed|prescription|medicine|"
    r"medication|metformin|insulin|thyroid)\b|\b(?:stop|skip)\b.{0,60}\b(?:natural|home|herbal)\s+remed",
    re.IGNORECASE,
)
_PRESCRIBING_REQUEST = re.compile(
    r"\b(?:what|which)\s+(?:medicine|medication|drug|antibiotic)\s+should\s+i\s+take\b|"
    r"\bprescribe\s+(?:me\s+)?(?:something|a\s+medicine|medication)\b|"
    r"\bwhat\s+should\s+i\s+take\s+for\b",
    re.IGNORECASE,
)
_HIGH_RISK = re.compile(
    r"\b(?:drink|inject|swallow|ingest|inhale)\b.{0,35}\b(?:bleach|disinfectant|cleaner|"
    r"hydrogen\s+peroxide)\b|\btake\b.{0,20}\b(?:handful|entire\s+bottle)\b",
    re.IGNORECASE,
)
_DRAFT_MEDICATION = re.compile(
    r"\byou\s+(?:should|must|need\s+to|can)\s+(?:stop|start|change|double|increase|decrease|"
    r"skip|reduce|switch)\b|\b(?:stop|double|increase|decrease)\s+(?:your\s+)?dose\b",
    re.IGNORECASE,
)
_DRAFT_PRESCRIBING = re.compile(
    r"\bi\s+(?:recommend|prescribe)\b.{0,45}\b(?:take|start|use)\b|"
    r"\b(?:take|start)\s+\d+(?:\.\d+)?\s*(?:mg|mcg|ml)\b",
    re.IGNORECASE,
)
_DRAFT_REPLACEMENT = re.compile(
    r"\b(?:you\s+(?:can|should)|natural|home|herbal)\b.{0,55}\b(?:replace|instead\s+of)\b"
    r".{0,45}\b(?:prescribed|prescription|medicine|medication|drug)\b",
    re.IGNORECASE,
)


def match_medication_pre(text: str) -> RuleMatch | None:
    if _HIGH_RISK.search(text):
        return RuleMatch(
            SafetyDecision.BLOCK,
            SafetyCategory.HIGH_RISK_SELF_TREATMENT,
            "SAFE-SELF-001",
            "Potentially dangerous self-treatment instructions are blocked.",
            HIGH_RISK_RESPONSE,
            professional=True,
        )
    if _TREATMENT_REPLACEMENT.search(text):
        return RuleMatch(
            SafetyDecision.BLOCK,
            SafetyCategory.TREATMENT_REPLACEMENT,
            "SAFE-TREAT-001",
            "Replacing prescribed treatment is outside this system's role.",
            REPLACEMENT_RESPONSE,
            professional=True,
        )
    if _CHANGE_REQUEST.search(text):
        return RuleMatch(
            SafetyDecision.BLOCK,
            SafetyCategory.MEDICATION_CHANGE,
            "SAFE-MED-001",
            "Medication-change instructions are blocked.",
            MEDICATION_RESPONSE,
            professional=True,
        )
    if _PRESCRIBING_REQUEST.search(text):
        return RuleMatch(
            SafetyDecision.BLOCK,
            SafetyCategory.PRESCRIBING_REQUEST,
            "SAFE-RX-001",
            "Prescribing requests are outside this system's role.",
            PRESCRIBING_RESPONSE,
            professional=True,
        )
    return None


def match_medication_post(draft: str) -> RuleMatch | None:
    if _DRAFT_REPLACEMENT.search(draft):
        return RuleMatch(
            SafetyDecision.BLOCK,
            SafetyCategory.TREATMENT_REPLACEMENT,
            "SAFE-TREAT-POST-001",
            "Unsafe treatment-replacement instructions were removed.",
            REPLACEMENT_RESPONSE,
            professional=True,
        )
    if _DRAFT_MEDICATION.search(draft):
        return RuleMatch(
            SafetyDecision.BLOCK,
            SafetyCategory.MEDICATION_CHANGE,
            "SAFE-MED-POST-001",
            "Unsafe medication-change instructions were removed.",
            UNSAFE_DRAFT_RESPONSE,
            professional=True,
        )
    if _DRAFT_PRESCRIBING.search(draft):
        return RuleMatch(
            SafetyDecision.BLOCK,
            SafetyCategory.PRESCRIBING_REQUEST,
            "SAFE-RX-POST-001",
            "Unsafe prescribing instructions were removed.",
            UNSAFE_DRAFT_RESPONSE,
            professional=True,
        )
    return None
