"""Optional constrained explanation after authoritative calculation."""

import json
from typing import Any

from app.analytics.schemas import ExplanationSource, TrendClassification
from app.llm.base import LLMProvider
from app.llm.types import LLMError


def template_explanation(data: dict[str, Any]) -> str:
    recent = data["recent_summary"]["mean"]
    baseline = data["baseline_summary"]["mean"]
    label = data["metric_label"]
    context = data.get("context")
    prefix = f"{context.replace('_', ' ').title()} {label.lower()}" if context else label
    if data["classification"] == TrendClassification.INSUFFICIENT_DATA:
        return f"Not enough recorded {prefix.lower()} data is available to compare these periods."
    return (
        f"Your recent {prefix.lower()} average was {recent:g} {data['unit']} compared with "
        f"{baseline:g} {data['unit']} in your personal baseline. "
        f"The deterministic classification is {data['classification'].lower()}."
    )


def explain_result(
    provider: LLMProvider,
    data: dict[str, Any],
    *,
    use_llm: bool,
) -> tuple[str, ExplanationSource]:
    fallback = template_explanation(data)
    if not use_llm or not provider.health_check():
        return fallback, ExplanationSource.TEMPLATE
    prompt = (
        "Explain this completed deterministic calculation in plain language. Do not diagnose, "
        "infer causes, change numbers, or add recommendations. Echo the supplied classification "
        "and means exactly.\nCALCULATION:\n" + json.dumps(data, default=str, sort_keys=True)
    )
    schema = {
        "type": "object",
        "required": ["explanation", "classification", "recent_mean", "baseline_mean"],
        "properties": {
            "explanation": {"type": "string"},
            "classification": {"type": "string"},
            "recent_mean": {"type": ["number", "null"]},
            "baseline_mean": {"type": ["number", "null"]},
        },
    }
    try:
        response = json.loads(provider.generate_structured(prompt, schema))
        if (
            response.get("classification") != str(data["classification"])
            or response.get("recent_mean") != data["recent_summary"]["mean"]
            or response.get("baseline_mean") != data["baseline_summary"]["mean"]
            or not isinstance(response.get("explanation"), str)
        ):
            return fallback, ExplanationSource.TEMPLATE
        return response["explanation"], ExplanationSource.LLM
    except (LLMError, ValueError, TypeError, json.JSONDecodeError):
        return fallback, ExplanationSource.TEMPLATE
