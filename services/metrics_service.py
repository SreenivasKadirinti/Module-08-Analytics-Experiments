from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date, datetime
from typing import Optional
from app.models.tables import StagingEvent
from app.core.time_utils import utc_day_bounds

def get_basic_metrics(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    placement_id: Optional[str] = None,
    model_version: Optional[str] = None
):
    """
    Calculate basic metrics with optional filters
    """
    filters = []

    if start_date:
        filters.append(StagingEvent.occurred_at >= utc_day_bounds(start_date)[0])
    if end_date:
        filters.append(StagingEvent.occurred_at < utc_day_bounds(end_date)[1])
    if placement_id:
        filters.append(StagingEvent.placement_id == placement_id)
    if model_version:
        filters.append(StagingEvent.model_version == model_version)

    def count_event(event_type: str) -> int:
        query = db.query(func.count(StagingEvent.id)).filter(StagingEvent.event_type == event_type)
        if filters:
            query = query.filter(and_(*filters))
        return query.scalar() or 0

    total_impressions = count_event("impression")
    total_clicks = count_event("click")
    total_add_to_carts = count_event("add_to_cart")
    total_purchases = count_event("purchase")

    ctr = round((total_clicks / total_impressions) * 100, 2) if total_impressions > 0 else 0.0
    conversion_rate = round((total_purchases / total_clicks) * 100, 2) if total_clicks > 0 else 0.0

    return {
        "filters": {
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
            "placement_id": placement_id,
            "model_version": model_version
        },
        "impressions": total_impressions,
        "clicks": total_clicks,
        "add_to_carts": total_add_to_carts,
        "purchases": total_purchases,
        "ctr_percent": ctr,
        "conversion_rate_percent": conversion_rate
    }


def get_metrics_by_placement(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    model_version: Optional[str] = None
):
    """
    Breakdown of metrics by placement with optional filters
    """
    filters = []

    if start_date:
        filters.append(StagingEvent.occurred_at >= utc_day_bounds(start_date)[0])
    if end_date:
        filters.append(StagingEvent.occurred_at < utc_day_bounds(end_date)[1])
    if model_version:
        filters.append(StagingEvent.model_version == model_version)

    query = db.query(
        StagingEvent.placement_id,
        StagingEvent.event_type,
        func.count(StagingEvent.id).label("count")
    )

    if filters:
        query = query.filter(and_(*filters))

    results = query.group_by(
        StagingEvent.placement_id,
        StagingEvent.event_type
    ).all()

    metrics = {}
    for row in results:
        placement = row.placement_id or "unknown"
        if placement not in metrics:
            metrics[placement] = {
                "impressions": 0,
                "clicks": 0,
                "add_to_carts": 0,
                "purchases": 0
            }

        if row.event_type == "impression":
            metrics[placement]["impressions"] = row.count
        elif row.event_type == "click":
            metrics[placement]["clicks"] = row.count
        elif row.event_type == "add_to_cart":
            metrics[placement]["add_to_carts"] = row.count
        elif row.event_type == "purchase":
            metrics[placement]["purchases"] = row.count

    # Add CTR for each placement
    for placement, data in metrics.items():
        impressions = data["impressions"]
        clicks = data["clicks"]
        data["ctr_percent"] = round((clicks / impressions) * 100, 2) if impressions > 0 else 0.0

    return metrics