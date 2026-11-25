import logging
from datetime import date
from typing import Optional
from app.core.auth import Role, require_role

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.time_utils import utc_today
from app.database.connection import get_db
from app.models.tables import FactDailyMetrics
from app.services.aggregation_service import aggregate_daily_metrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/aggregation", tags=["Aggregation"])


@router.post("/run", dependencies=[Depends(require_role(Role.SERVICE))])
def run_aggregation(
    target_date: Optional[date] = Query(None, description="UTC date (YYYY-MM-DD). Defaults to today."),
    db: Session = Depends(get_db),
):
    day = target_date or utc_today()
    if day > utc_today():
        raise HTTPException(status_code=400, detail="target_date cannot be in the future")

    try:
        result = aggregate_daily_metrics(db, day)
    except Exception:
        db.rollback()
        logger.exception("Aggregation failed for %s", day)
        raise HTTPException(status_code=500, detail="Aggregation failed")

    if result["records_created"] == 0:
        result["status"] = "no_data"
        result["message"] = f"No events found for {day}; nothing was aggregated"
    return result


@router.get("/daily-metrics", dependencies=[Depends(require_role(Role.SERVICE))])
def get_daily_metrics(
    response: Response,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    placement_id: Optional[str] = Query(None),
    model_version: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date")

    query = db.query(FactDailyMetrics)
    if start_date:
        query = query.filter(FactDailyMetrics.metric_date >= start_date)
    if end_date:
        query = query.filter(FactDailyMetrics.metric_date <= end_date)
    if placement_id:
        query = query.filter(FactDailyMetrics.placement_id == placement_id)
    if model_version:
        query = query.filter(FactDailyMetrics.model_version == model_version)
    if category_id:
        query = query.filter(FactDailyMetrics.category_id == category_id)

    response.headers["X-Total-Count"] = str(query.count())

    rows = (
        query.order_by(
            FactDailyMetrics.metric_date.desc(),
            FactDailyMetrics.placement_id,
            FactDailyMetrics.model_version,
            FactDailyMetrics.category_id,
            FactDailyMetrics.id,
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        {
            "id": r.id,
            "metric_date": str(r.metric_date),
            "placement_id": r.placement_id,
            "model_version": r.model_version,
            "category_id": r.category_id,
            "impressions": r.impressions,
            "clicks": r.clicks,
            "add_to_carts": r.add_to_carts,
            "purchases": r.purchases,
            "unique_users": r.unique_users,
            "unique_sessions": r.unique_sessions,
            "ctr": r.ctr,
            "atc_rate": r.atc_rate,
            "conversion_rate": r.conversion_rate,
            "purchase_rate_from_atc": r.purchase_rate_from_atc,
            "revenue": r.revenue,
            "aov": r.aov,
            "revenue_per_impression": r.revenue_per_impression,
            "revenue_per_click": r.revenue_per_click,
        }
        for r in rows
    ]