from datetime import date

from sqlalchemy import and_, exists, func, literal_column
from sqlalchemy.orm import Session, aliased

from app.core.constants import CLICK_WINDOW, PURCHASE_WINDOW, REVENUE_KEYS
from app.core.time_utils import utc_day_bounds, utc_today
from app.models.tables import DimProduct, FactDailyMetrics, StagingEvent

# Events whose product is missing from dim_product fall into 'unknown'.
CATEGORY = func.coalesce(DimProduct.category_id, literal_column("'unknown'"))


def _extract_revenue(raw_payload) -> float:
    if not raw_payload or not isinstance(raw_payload, dict):
        return 0.0
    for key in REVENUE_KEYS:
        val = raw_payload.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return 0.0


def _row(aggregated: dict, placement_id, model_version, category_id) -> dict:
    key = (placement_id, model_version, category_id)
    if key not in aggregated:
        aggregated[key] = {
            "placement_id": placement_id, 
            "model_version": model_version,
            "category_id": category_id,
            "impressions": 0, "clicks": 0, "add_to_carts": 0, "purchases": 0,
            "unique_users": 0, "unique_sessions": 0, "revenue": 0.0,
            "clicked_impressions": 0, "converted_impressions": 0,
            "unattributed_clicks": 0, "unattributed_purchases": 0,
        }
    return aggregated[key]


def _cohort_counts(db: Session, day_start, day_end, etype: str, window):
    """Impressions of the day that received >= 1 event of `etype` within `window`."""
    I = aliased(StagingEvent)
    E = aliased(StagingEvent)
    return (
        db.query(I.placement_id, I.model_version, CATEGORY.label("category_id"),
                 func.count(func.distinct(I.id)).label("n"))
        .select_from(I)
        .join(E, and_(
            E.impression_id == I.impression_id,
            E.event_type == etype,
            E.occurred_at >= I.occurred_at,
            E.occurred_at < I.occurred_at + window,
        ))
        .outerjoin(DimProduct, I.product_id == DimProduct.product_id)
        .filter(I.event_type == "impression",
                I.occurred_at >= day_start, I.occurred_at < day_end)
        .group_by(I.placement_id, I.model_version, CATEGORY)
        .all()
    )


def aggregate_daily_metrics(db: Session, target_date: date = None):
    """
    Aggregate one UTC day into fact_daily_metrics.
    Grain: (metric_date, placement_id, model_version, category_id).
    Event counts are by event date; linked-funnel counts are by impression date.
    """
    if target_date is None:
        target_date = utc_today()

    day_start, day_end = utc_day_bounds(target_date)
    in_day = (StagingEvent.occurred_at >= day_start, StagingEvent.occurred_at < day_end)
    join_cond = StagingEvent.product_id == DimProduct.product_id

    db.query(FactDailyMetrics).filter(FactDailyMetrics.metric_date == target_date).delete()
    aggregated: dict = {}

    # 1. Event counts by type
    for r in (
        db.query(StagingEvent.placement_id, StagingEvent.model_version,
                 CATEGORY.label("category_id"), StagingEvent.event_type,
                 func.count(StagingEvent.id).label("count"))
        .outerjoin(DimProduct, join_cond).filter(*in_day)
        .group_by(StagingEvent.placement_id, StagingEvent.model_version,
                  CATEGORY, StagingEvent.event_type)
        .all()
    ):
        row = _row(aggregated, r.placement_id, r.model_version, r.category_id)
        field = {"impression": "impressions", "click": "clicks",
                 "add_to_cart": "add_to_carts", "purchase": "purchases"}.get(r.event_type)
        if field:
            row[field] = r.count

    # 2. Unique users & sessions (per row)
    for r in (
        db.query(StagingEvent.placement_id, StagingEvent.model_version,
                 CATEGORY.label("category_id"),
                 func.count(func.distinct(StagingEvent.user_ref)).label("uu"),
                 func.count(func.distinct(StagingEvent.session_id)).label("us"))
        .outerjoin(DimProduct, join_cond).filter(*in_day)
        .group_by(StagingEvent.placement_id, StagingEvent.model_version, CATEGORY)
        .all()
    ):
        row = _row(aggregated, r.placement_id, r.model_version, r.category_id)
        row["unique_users"], row["unique_sessions"] = r.uu or 0, r.us or 0

    # 3. Revenue from purchase payloads
    for r in (
        db.query(StagingEvent.placement_id, StagingEvent.model_version,
                 CATEGORY.label("category_id"), StagingEvent.raw_payload)
        .outerjoin(DimProduct, join_cond)
        .filter(*in_day, StagingEvent.event_type == "purchase")
        .all()
    ):
        row = _row(aggregated, r.placement_id, r.model_version, r.category_id)
        row["revenue"] += _extract_revenue(r.raw_payload)

    # 4. Linked cohorts: impressions of this day that got a click / purchase in the window
    for etype, window, field in (
        ("click", CLICK_WINDOW, "clicked_impressions"),
        ("purchase", PURCHASE_WINDOW, "converted_impressions"),
    ):
        for r in _cohort_counts(db, day_start, day_end, etype, window):
            _row(aggregated, r.placement_id, r.model_version, r.category_id)[field] = r.n

    # 5. Unattributed: clicks / purchases of this day with no matching earlier impression
    for etype, window, field in (
        ("click", CLICK_WINDOW, "unattributed_clicks"),
        ("purchase", PURCHASE_WINDOW, "unattributed_purchases"),
    ):
        I = aliased(StagingEvent)
        matched = exists().where(and_(
            I.impression_id == StagingEvent.impression_id,
            I.event_type == "impression",
            I.occurred_at <= StagingEvent.occurred_at,
            I.occurred_at >= StagingEvent.occurred_at - window,
        )).correlate(StagingEvent)
        for r in (
            db.query(StagingEvent.placement_id, StagingEvent.model_version,
                     CATEGORY.label("category_id"), func.count(StagingEvent.id).label("n"))
            .outerjoin(DimProduct, join_cond)
            .filter(*in_day, StagingEvent.event_type == etype, ~matched)
            .group_by(StagingEvent.placement_id, StagingEvent.model_version, CATEGORY)
            .all()
        ):
            _row(aggregated, r.placement_id, r.model_version, r.category_id)[field] = r.n

    # 6. Write fact rows
    for d in aggregated.values():
        imp, clk, atc, pur = d["impressions"], d["clicks"], d["add_to_carts"], d["purchases"]
        revenue = round(d["revenue"], 2)
        db.add(FactDailyMetrics(
            metric_date=target_date,
            placement_id=d["placement_id"], model_version=d["model_version"],
            category_id=d["category_id"],
            impressions=imp, clicks=clk, add_to_carts=atc, purchases=pur,
            unique_users=d["unique_users"], unique_sessions=d["unique_sessions"],
            clicked_impressions=d["clicked_impressions"],
            converted_impressions=d["converted_impressions"],
            unattributed_clicks=d["unattributed_clicks"],
            unattributed_purchases=d["unattributed_purchases"],
            ctr=round(clk / imp * 100, 2) if imp else 0.0,
            atc_rate=round(atc / clk * 100, 2) if clk else 0.0,
            conversion_rate=round(pur / clk * 100, 2) if clk else 0.0,
            purchase_rate_from_atc=round(pur / atc * 100, 2) if atc else 0.0,
            revenue=revenue,
            aov=round(revenue / pur, 2) if pur else 0.0,
            revenue_per_impression=round(revenue / imp, 4) if imp else 0.0,
            revenue_per_click=round(revenue / clk, 4) if clk else 0.0,
        ))

    db.commit()
    return {
        "status": "success",
        "date": str(target_date),
        "records_created": len(aggregated),
        "message": f"Daily metrics aggregated successfully for {target_date}",
    }