"""Clinical-date ordering for normalized timeline items."""

from app.timeline.schemas import TimelineItem


def order_timeline_items(items: list[TimelineItem], sort: str) -> list[TimelineItem]:
    dated = [item for item in items if item.occurred_at is not None]
    unknown = [item for item in items if item.occurred_at is None]
    reverse = sort == "desc"
    dated.sort(
        key=lambda item: (item.occurred_at.timestamp(), item.created_at.timestamp(), item.id),
        reverse=reverse,
    )
    unknown.sort(key=lambda item: (item.created_at.timestamp(), item.id), reverse=reverse)
    return [*dated, *unknown]
