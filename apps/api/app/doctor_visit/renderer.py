"""Optional constrained readability rewrite with fact and safety validation."""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from app.doctor_visit.schemas import RewriteStatus
from app.llm.base import LLMProvider
from app.llm.types import LLMError
from app.safety.enums import SafetyDecision
from app.safety.schemas import SafetyInput, SafetyResult
from app.safety.service import SafetyService

_NUMBER = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?")


@dataclass(frozen=True)
class RewriteResult:
    overview: str
    source: str
    status: RewriteStatus
    safety: SafetyResult | None = None


def deterministic_overview(facts: dict[str, Any]) -> str:
    return (
        f"This brief summarizes {facts['history_count']} known history item(s), "
        f"{facts['medication_count']} current medication(s), {facts['lab_count']} recent lab "
        f"result(s), and {facts['change_count']} supported recent change(s) from trusted records."
    )


def rewrite_overview(
    provider: LLMProvider,
    safety: SafetyService,
    facts: dict[str, Any],
    *,
    enabled: bool,
    profile_id: str,
) -> RewriteResult:
    fallback = deterministic_overview(facts)
    if not enabled:
        return RewriteResult(fallback, "TEMPLATE", RewriteStatus.NOT_REQUESTED)
    if not provider.health_check():
        return RewriteResult(fallback, "TEMPLATE", RewriteStatus.UNAVAILABLE)
    canonical = json.dumps(facts, sort_keys=True, separators=(",", ":"), default=str)
    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
    prompt = (
        "Rewrite the supplied overview for readability only. Do not add or remove facts, change "
        "numbers, diagnose, prescribe, or recommend treatment. Return JSON with overview and the "
        f"unchanged facts_fingerprint.\nOVERVIEW: {fallback}\nFACTS: {canonical}\n"
        f"FACTS_FINGERPRINT: {fingerprint}"
    )
    schema = {
        "type": "object",
        "required": ["overview", "facts_fingerprint"],
        "properties": {
            "overview": {"type": "string"},
            "facts_fingerprint": {"type": "string"},
        },
    }
    try:
        response = json.loads(provider.generate_structured(prompt, schema))
        candidate = response.get("overview")
        if not isinstance(candidate, str) or response.get("facts_fingerprint") != fingerprint:
            return RewriteResult(fallback, "TEMPLATE", RewriteStatus.INVALID_RESPONSE)
        if sorted(_NUMBER.findall(candidate)) != sorted(_NUMBER.findall(fallback)):
            return RewriteResult(fallback, "TEMPLATE", RewriteStatus.REJECTED_FACT_CHANGE)
        safety_result = safety.post_check(
            SafetyInput(
                user_text="Prepare a doctor visit record summary.",
                draft_response=candidate,
                profile_id=profile_id,
                context_type="DOCTOR_VISIT",
                source="DOCTOR_VISIT_LLM_REWRITE",
            )
        )
        if safety_result.decision not in {
            SafetyDecision.ALLOW,
            SafetyDecision.ALLOW_WITH_NOTICE,
        }:
            return RewriteResult(
                fallback,
                "TEMPLATE",
                RewriteStatus.REJECTED_SAFETY,
                safety_result,
            )
        return RewriteResult(candidate, "LLM", RewriteStatus.LLM_ACCEPTED, safety_result)
    except (LLMError, ValueError, TypeError, json.JSONDecodeError):
        return RewriteResult(fallback, "TEMPLATE", RewriteStatus.INVALID_RESPONSE)
