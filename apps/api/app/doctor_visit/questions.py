"""Conservative deterministic visit-discussion questions."""

from app.doctor_visit.schemas import (
    DiscussionQuestion,
    RecentChangeItem,
    VisitMissingEvidenceItem,
)


def build_questions(
    changes: list[RecentChangeItem], missing: list[VisitMissingEvidenceItem]
) -> list[DiscussionQuestion]:
    questions: list[DiscussionQuestion] = []
    if any(item.type == "MISSING_RECENT_THYROID_LAB" for item in missing):
        questions.append(
            DiscussionQuestion(
                question_id="VISIT-Q-THYROID-001",
                trigger="MISSING_RECENT_LAB",
                question="Would updated thyroid testing be useful to discuss?",
            )
        )
    if any(item.type == "STALE_MEDICATION_REVIEW" for item in missing):
        questions.append(
            DiscussionQuestion(
                question_id="VISIT-Q-MED-001",
                trigger="STALE_MEDICATION_REVIEW",
                question="Can the current medication list be reconciled?",
            )
        )
    for change in changes[:3]:
        context = (
            f"{change.analysis.context.value.replace('_', ' ').lower()} "
            if change.analysis.context
            else ""
        )
        questions.append(
            DiscussionQuestion(
                question_id=f"VISIT-Q-TREND-{change.key.upper().replace(':', '-')}",
                trigger="RECENT_TREND",
                question=(
                    f"Should the recent {context}{change.analysis.metric_label.lower()} trend "
                    "be reviewed during the visit?"
                ),
            )
        )
    return questions
