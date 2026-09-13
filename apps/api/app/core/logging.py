"""Small JSON logging foundation for application lifecycle events."""

import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Render predictable structured logs without including sensitive context."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if environment := getattr(record, "environment", None):
            payload["environment"] = environment
        for field in (
            "request_id",
            "agent_intent",
            "agent_nodes",
            "duration_ms",
            "result_status",
            "safety_decision",
            "safety_category",
            "safety_rule_id",
            "safety_policy_version",
        ):
            if value := getattr(record, field, None):
                payload[field] = value
        return json.dumps(payload)


def configure_logging() -> None:
    """Configure application logging once with a compact JSON formatter."""

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Secrets and request health data are intentionally excluded because later
    # phases may process highly sensitive personal health information.
