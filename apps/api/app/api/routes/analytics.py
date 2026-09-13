"""Profile-scoped deterministic analytics endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics.schemas import (
    AnalyticsMetric,
    AvailableMetricsResponse,
    GlucoseContext,
    SymptomFrequencyResult,
    TrendAnalysisResult,
    WhatChangedRequest,
    WhatChangedResponse,
)
from app.analytics.service import AnalyticsService
from app.database.session import get_db
from app.llm.base import LLMProvider
from app.llm.factory import get_llm_provider

router = APIRouter(tags=["analytics"])


def get_analytics_service(
    llm: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> AnalyticsService:
    return AnalyticsService(llm)


@router.get(
    "/profiles/{profile_id}/analytics/trends",
    response_model=TrendAnalysisResult,
)
def get_numeric_trend(
    profile_id: str,
    metric: AnalyticsMetric,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    context: GlucoseContext | None = None,
    reference_date: date | None = None,
    recent_days: Annotated[int | None, Query(ge=1, le=365)] = None,
    baseline_days: Annotated[int | None, Query(ge=1, le=730)] = None,
    include_explanation: bool = False,
) -> TrendAnalysisResult:
    return service.trend(
        db,
        profile_id,
        metric,
        context=context,
        reference_date=reference_date,
        recent_days=recent_days,
        baseline_days=baseline_days,
        include_explanation=include_explanation,
    )


@router.get(
    "/profiles/{profile_id}/analytics/symptoms/{symptom_name}",
    response_model=SymptomFrequencyResult,
)
def get_symptom_frequency(
    profile_id: str,
    symptom_name: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    reference_date: date | None = None,
    recent_days: Annotated[int | None, Query(ge=1, le=365)] = None,
    baseline_days: Annotated[int | None, Query(ge=1, le=730)] = None,
) -> SymptomFrequencyResult:
    return service.symptom_frequency(
        db,
        profile_id,
        symptom_name,
        reference_date=reference_date,
        recent_days=recent_days,
        baseline_days=baseline_days,
    )


@router.get(
    "/profiles/{profile_id}/analytics/metrics",
    response_model=AvailableMetricsResponse,
)
def get_available_metrics(
    profile_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> AvailableMetricsResponse:
    return service.available_metrics(db, profile_id)


@router.post(
    "/profiles/{profile_id}/analytics/what-changed",
    response_model=WhatChangedResponse,
)
def get_what_changed(
    profile_id: str,
    request: WhatChangedRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> WhatChangedResponse:
    return service.what_changed(db, profile_id, request)
