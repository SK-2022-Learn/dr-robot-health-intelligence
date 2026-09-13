"""Deterministic personal-baseline analytics node."""

from sqlalchemy.orm import Session

from app.agents.state import DrRobotState
from app.analytics.schemas import AnalyticsMetric, GlucoseContext, WhatChangedRequest
from app.analytics.service import AnalyticsService


def _metric(query: str) -> AnalyticsMetric | None:
    text = query.casefold()
    if "hba1c" in text or "a1c" in text:
        return AnalyticsMetric.HBA1C
    if "glucose" in text or "sugar" in text:
        return AnalyticsMetric.GLUCOSE
    if "weight" in text:
        return AnalyticsMetric.WEIGHT
    if "blood pressure" in text or "systolic" in text:
        return AnalyticsMetric.SYSTOLIC_BLOOD_PRESSURE
    if "sleep" in text:
        return AnalyticsMetric.SLEEP_DURATION
    if "activity" in text or "walk" in text:
        return AnalyticsMetric.ACTIVITY_DURATION
    return None


def analytics_node(db: Session, service: AnalyticsService):
    def run(state: DrRobotState) -> dict:
        query = state["user_query"]
        metric = _metric(query)
        if metric is None:
            response = service.what_changed(
                db, state["profile_id"], WhatChangedRequest(include_explanation=False)
            )
            data = response.model_dump(mode="json")
            if response.results:
                answer = response.results[0].explanation
            else:
                answer = "No verified numeric history is available for a baseline comparison."
        else:
            context = None
            normalized = query.casefold()
            if metric == AnalyticsMetric.GLUCOSE:
                if "post-meal" in normalized or "after meal" in normalized:
                    context = GlucoseContext.AFTER_MEAL
                elif "fasting" in normalized or "before food" in normalized:
                    context = GlucoseContext.FASTING
                elif "before meal" in normalized:
                    context = GlucoseContext.BEFORE_MEAL
            result = service.trend(
                db,
                state["profile_id"],
                metric,
                context=context,
                include_explanation=False,
            )
            data = result.model_dump(mode="json")
            answer = result.explanation
        return {
            "analytics_context": data,
            "draft_response": answer,
            "actions_taken": ["deterministic_analytics"],
            "nodes_run": ["analytics"],
        }

    return run
