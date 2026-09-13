"""Unsupported cure and treatment-claim rules."""

import re

from app.safety.enums import SafetyCategory, SafetyDecision
from app.safety.policy import CURE_RESPONSE, RuleMatch

_CURE_CLAIM = re.compile(
    r"\b(?:herb|remedy|turmeric|supplement|natural\s+treatment)\b.{0,50}"
    r"\b(?:cures?|eliminates?|reverses?)\b|"
    r"\b(?:cures?|eliminates?)\b.{0,50}\b(?:diabetes|cancer|thyroid\s+disease)\b",
    re.IGNORECASE,
)


def match_cure_claim(text: str, *, post_check: bool = False) -> RuleMatch | None:
    if not _CURE_CLAIM.search(text):
        return None
    return RuleMatch(
        SafetyDecision.BLOCK,
        SafetyCategory.UNSUPPORTED_CURE_CLAIM,
        "SAFE-CURE-POST-001" if post_check else "SAFE-CURE-001",
        "An unsupported cure claim was blocked.",
        CURE_RESPONSE,
        professional=True,
    )
