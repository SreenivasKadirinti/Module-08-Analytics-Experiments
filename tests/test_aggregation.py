from datetime import date, datetime, timezone, timedelta
import pytest
from sqlalchemy.exc import IntegrityError
from app.models.tables import StagingEvent, FactDailyMetrics, DimProduct
from app.services.aggregation_service import aggregate_daily_metrics


D = date(2026, 11, 13)

def ev(etype, ts, **kw):
    return StagingEvent(
        event_type=etype, occurred_at=ts,
        placement_id=kw.pop("placement_id", "home_carousel"),
        model_version="v1", **kw,
    )

def test_known_funnel(db):
    t = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)
    for i in range(10):
        db.add(ev("impression", t, user_ref=f"u{i % 5}", session_id=f"s{i % 2}"))
    for _ in range(3):
        db.add(ev("click", t, user_ref="u0", session_id="s0"))
    for _ in range(2):
        db.add(ev("add_to_cart", t, user_ref="u0", session_id="s0"))
    db.add(ev("purchase", t, user_ref="u0", session_id="s0",
              raw_payload={"amount": 89.25}))
    db.commit()

    aggregate_daily_metrics(db, D)
    r = db.query(FactDailyMetrics).one()

    assert (r.impressions, r.clicks, r.add_to_carts, r.purchases) == (10, 3, 2, 1)
    assert r.unique_users == 5 and r.unique_sessions == 2
    assert r.ctr == 30.0
    assert r.atc_rate == 66.67
    assert r.conversion_rate == 33.33
    assert r.purchase_rate_from_atc == 50.0
    assert r.revenue == 89.25 and r.aov == 89.25
    assert r.revenue_per_click == 29.75

def test_utc_day_boundaries(db):
    ist = timezone(timedelta(hours=5, minutes=30))
    db.add(ev("impression", datetime(2026, 11, 13, 23, 30, tzinfo=timezone.utc)))  # in
    db.add(ev("impression", datetime(2026, 11, 14, 4, 30, tzinfo=ist)))            # 23:00Z, in
    db.add(ev("impression", datetime(2026, 11, 14, 0, 30, tzinfo=timezone.utc)))   # out
    db.commit()

    aggregate_daily_metrics(db, D)
    assert db.query(FactDailyMetrics).one().impressions == 2

def test_rerun_is_idempotent(db):
    db.add(ev("impression", datetime(2026, 11, 13, 9, 0, tzinfo=timezone.utc)))
    db.commit()
    aggregate_daily_metrics(db, D)
    aggregate_daily_metrics(db, D)
    assert db.query(FactDailyMetrics).count() == 1

def test_duplicate_event_id_rejected(db):
    t = datetime(2026, 11, 13, 9, 0, tzinfo=timezone.utc)
    db.add(ev("click", t, event_id="evt-1"))
    db.commit()
    db.add(ev("click", t, event_id="evt-1"))
    with pytest.raises(IntegrityError):
        db.commit()
def _products(db):
    db.add_all([
        DimProduct(product_id="P1", category_id="Electronics"),
        DimProduct(product_id="P2", category_id="Fashion"),
    ])
    db.commit()

T = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)

def test_two_categories_sum_to_totals(db):
    _products(db)
    for _ in range(3): db.add(ev("impression", T, product_id="P1", user_ref="u1"))
    for _ in range(2): db.add(ev("impression", T, product_id="P2", user_ref="u2"))
    db.add(ev("click", T, product_id="P1", user_ref="u1"))
    db.add(ev("purchase", T, product_id="P2", user_ref="u2", raw_payload={"amount": 50}))
    db.commit()

    aggregate_daily_metrics(db, D)
    rows = {r.category_id: r for r in db.query(FactDailyMetrics).all()}

    assert set(rows) == {"Electronics", "Fashion"}
    assert (rows["Electronics"].impressions, rows["Electronics"].clicks) == (3, 1)
    assert (rows["Fashion"].impressions, rows["Fashion"].purchases) == (2, 1)
    assert rows["Fashion"].revenue == 50.0
    # category rows add up to the overall counts and revenue
    assert sum(r.impressions for r in rows.values()) == 5
    assert sum(r.revenue for r in rows.values()) == 50.0

def test_unknown_product_goes_to_unknown(db):
    _products(db)
    db.add(ev("impression", T, product_id="NOT_IN_DIM"))
    db.add(ev("impression", T))   # no product_id at all
    db.commit()

    aggregate_daily_metrics(db, D)
    r = db.query(FactDailyMetrics).one()
    assert r.category_id == "unknown" and r.impressions == 2

def test_user_in_two_categories_counts_in_each(db):
    _products(db)
    db.add(ev("impression", T, product_id="P1", user_ref="u1"))
    db.add(ev("impression", T, product_id="P2", user_ref="u1"))
    db.commit()

    aggregate_daily_metrics(db, D)
    rows = db.query(FactDailyMetrics).all()
    assert [r.unique_users for r in rows] == [1, 1]   # sums to 2, but only 1 real user