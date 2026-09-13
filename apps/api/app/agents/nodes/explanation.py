"""Plain-language rendering over facts already selected by authoritative services."""

import json

from app.agents.schemas import AgentIntent
from app.agents.state import DrRobotState
from app.llm.base import LLMProvider
from app.llm.types import LLMError


def explanation_node(provider: LLMProvider):
    def run(state: DrRobotState) -> dict:
        intent = state["intent"]
        if state.get("draft_response"):
            return {"nodes_run": ["explanation"]}
        if intent == AgentIntent.UNSUPPORTED_MEDICAL_ACTION:
            answer = (
                "I can organize your records, but medication changes, prescribing, and diagnosis "
                "require an appropriate clinician or pharmacist."
            )
            return {"draft_response": answer, "nodes_run": ["explanation"]}
        if intent == AgentIntent.UNKNOWN:
            return {
                "draft_response": (
                    "I’m not sure which record workflow you want. Ask me to log a reading, find a "
                    "record, explain evidence, compare a trend, review family patterns, or prepare "
                    "a doctor visit brief."
                ),
                "clarification_required": True,
                "nodes_run": ["explanation"],
            }

        normalized = state["user_query"].casefold()
        if "hba1c" in normalized or "a1c" in normalized:
            return {
                "draft_response": (
                    "HbA1c is a blood test that summarizes average blood glucose over roughly "
                    "the previous two to three months. A result should be interpreted by a "
                    "clinician in the context of the individual’s health history."
                ),
                "actions_taken": ["deterministic_health_education"],
                "nodes_run": ["explanation"],
            }

        prompt = (
            "Provide concise, general health education only. Do not diagnose, prescribe, recommend "
            "a medication change, or claim access to patient records. User question: "
            + state["user_query"]
        )
        schema = {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        }
        try:
            payload = json.loads(provider.generate_structured(prompt, schema))
            answer = payload.get("answer") if isinstance(payload, dict) else None
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("missing answer")
        except (LLMError, ValueError, TypeError, json.JSONDecodeError):
            return {
                "draft_response": (
                    "General educational generation is currently unavailable. Record lookup, "
                    "timeline, analytics, family, evidence, and Doctor Visit features remain "
                    "usable."
                ),
                "warnings": ["The local language model is unavailable."],
                "nodes_run": ["explanation"],
            }
        return {
            "draft_response": answer.strip(),
            "actions_taken": ["general_explanation_generated"],
            "nodes_run": ["explanation"],
        }

    return run
