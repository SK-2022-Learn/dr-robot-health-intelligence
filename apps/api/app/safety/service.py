"""Authoritative deterministic Phase 11 safety service."""

import logging

from sqlalchemy.orm import Session

from app.safety.claims import match_cure_claim
from app.safety.enums import SafetyCategory, SafetyDecision
from app.safety.medication import match_medication_post, match_medication_pre
from app.safety.policy import POLICY_VERSION, RuleMatch
from app.safety.rules import (
    is_historical_report,
    is_logging,
    match_diagnosis_post,
    match_diagnosis_pre,
)
from app.safety.schemas import SafetyInput, SafetyResult
from app.safety.urgent import match_urgent
from app.services.audit import AuditService

logger = logging.getLogger("dr_robot.safety")


class SafetyService:
    """Apply versioned rules without asking an LLM to make policy decisions."""

    def __init__(self, audit: AuditService | None = None) -> None:
        self.audit = audit or AuditService()

    @staticmethod
    def _result(match: RuleMatch, stage: str) -> SafetyResult:
        return SafetyResult(
            decision=match.decision,
            category=match.category,
            rule_id=match.rule_id,
            message=match.message,
            safe_response_override=match.override,
            requires_professional_evaluation=match.professional,
            emergency_guidance=match.emergency,
            audit_metadata={"evaluation_stage": stage},
            policy_version=POLICY_VERSION,
        )

    @staticmethod
    def _allow(category: SafetyCategory, rule_id: str, stage: str) -> SafetyResult:
        return SafetyResult(
            decision=SafetyDecision.ALLOW,
            category=category,
            rule_id=rule_id,
            message="No safety intervention is required.",
            audit_metadata={"evaluation_stage": stage},
            policy_version=POLICY_VERSION,
        )

    def pre_check(self, data: SafetyInput) -> SafetyResult:
        text = data.user_text.strip()
        if is_historical_report(text):
            return self._allow(SafetyCategory.LOGGING_ONLY, "SAFE-HISTORY-001", "PRE")
        for match in (
            match_urgent(text),
            match_medication_pre(text),
            match_diagnosis_pre(text),
            match_cure_claim(text),
        ):
            if match is not None:
                return self._result(match, "PRE")
        if is_logging(text):
            return self._allow(SafetyCategory.LOGGING_ONLY, "SAFE-LOG-001", "PRE")
        return self._allow(
            SafetyCategory.GENERAL_HEALTH_INFORMATION,
            "SAFE-GEN-001",
            "PRE",
        )

    def post_check(self, data: SafetyInput) -> SafetyResult:
        draft = (data.draft_response or "").strip()
        if not draft:
            return self._allow(SafetyCategory.UNKNOWN, "SAFE-POST-ALLOW-001", "POST")
        for match in (
            match_medication_post(draft),
            match_diagnosis_post(draft),
            match_cure_claim(draft, post_check=True),
        ):
            if match is not None:
                return self._result(match, "POST")
        return self._allow(
            SafetyCategory.GENERAL_HEALTH_INFORMATION,
            "SAFE-POST-ALLOW-001",
            "POST",
        )

    def evaluate(self, data: SafetyInput) -> SafetyResult:
        pre_result = self.pre_check(data)
        if pre_result.decision not in {
            SafetyDecision.ALLOW,
            SafetyDecision.ALLOW_WITH_NOTICE,
        }:
            return pre_result
        return self.post_check(data) if data.draft_response is not None else pre_result

    def audit_result(
        self,
        db: Session,
        result: SafetyResult,
        *,
        entity_id: str,
        profile_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> None:
        action = {
            SafetyDecision.ALLOW: "SAFETY_ALLOW",
            SafetyDecision.ALLOW_WITH_NOTICE: "SAFETY_WARNING",
            SafetyDecision.WARN: "SAFETY_WARNING",
            SafetyDecision.BLOCK: "SAFETY_BLOCK",
            SafetyDecision.ESCALATE: "SAFETY_ESCALATION",
        }[result.decision]
        metadata = {
            "decision": result.decision.value,
            "category": result.category.value,
            "rule_id": result.rule_id,
            "policy_version": result.policy_version,
            "evaluation_stage": result.audit_metadata.get("evaluation_stage"),
        }
        if profile_id is not None:
            metadata["profile_id"] = profile_id
        self.audit.append(
            db,
            action=action,
            entity_type="safety_evaluation",
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            after_state=metadata,
        )
        logger.info(
            "Safety rule evaluated",
            extra={
                "safety_decision": result.decision.value,
                "safety_category": result.category.value,
                "safety_rule_id": result.rule_id,
                "safety_policy_version": result.policy_version,
            },
        )


def get_safety_service() -> SafetyService:
    return SafetyService()
