"""Versioned deterministic policy constants and safe response text."""

from dataclasses import dataclass

from app.safety.enums import SafetyCategory, SafetyDecision

POLICY_VERSION = "safety-v1"

URGENT_RESPONSE = (
    "Your message may describe an urgent medical situation. Please call emergency services now "
    "(911 in the U.S.) or go to the nearest emergency department. If possible, have someone stay "
    "with you. I cannot determine the cause or diagnose this here."
)
SELF_HARM_RESPONSE = (
    "Please seek immediate help now. Call emergency services if you may act on these thoughts. "
    "In the U.S. or Canada, call or text 988 for crisis support, and stay with a trusted person "
    "if you can."
)
MEDICATION_RESPONSE = (
    "I can help organize your medication history, but this system does not make medication-change "
    "decisions or tell you to stop, skip, double, or change a prescribed medication. Please "
    "discuss medication changes with your clinician or "
    "pharmacist. If you may be having a serious reaction, seek urgent medical evaluation."
)
DIAGNOSIS_RESPONSE = (
    "I can summarize your records and show supporting evidence, but I can't diagnose a condition. "
    "Please discuss diagnostic questions with an appropriate clinician."
)
PRESCRIBING_RESPONSE = (
    "I can provide general educational information, but I can't prescribe or choose a medication "
    "for you. Please ask an appropriate clinician or pharmacist."
)
CURE_RESPONSE = (
    "I can't endorse a claim that a remedy cures a disease. I can help review reliable recorded "
    "information, but treatment decisions should be discussed with an appropriate clinician."
)
REPLACEMENT_RESPONSE = (
    "I can't recommend replacing prescribed treatment with a home or natural remedy. Please "
    "discuss any treatment change with your clinician or pharmacist."
)
HIGH_RISK_RESPONSE = (
    "I can't help with that potentially dangerous self-treatment. Stop and contact a clinician, "
    "pharmacist, poison control center, or emergency service as appropriate."
)
UNSAFE_DRAFT_RESPONSE = (
    "I can't provide that medical instruction. I can help summarize your records or provide "
    "general educational information, but diagnosis, prescribing, and medication changes require "
    "an appropriate clinician or pharmacist."
)


@dataclass(frozen=True)
class RuleMatch:
    decision: SafetyDecision
    category: SafetyCategory
    rule_id: str
    message: str
    override: str | None = None
    professional: bool = False
    emergency: bool = False
