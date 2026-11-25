from datetime import datetime, timezone, date

from app.models.tables import FactDailyMetrics, StagingEvent
from app.services.aggregation_service import aggregate_daily_metrics
from app.services.reports_service import derive


def at(day, h, m=0):
    return datetime(2026, 11, day, h, m, tzinfo=timezone.utc)


def ev(etype, ts, imp=None, **kw):
    return StagingEvent(event_type=etype, occurred_at=ts, placement_id="p",
                        model_version="v1", impression_id=imp, **kw)


def rows(db):
    return {r.metric_date: r for r in db.query(FactDailyMetrics).all()}


def test_linked_cohort_windows_and_orphans(db):
    db.add_all([
        ev("impression", at(13, 10), "imp-1"),
        ev("impression", at(13, 10), "imp-2"),
        ev("impression", at(13, 10), "imp-3"),
        ev("click", at(13, 10, 5), "imp-1"),
        ev("click", at(13, 10, 6), "imp-1"),                 # 2nd click, same impression
        ev("click", at(13, 12), "ghost"),                    # orphan
        ev("click", at(14, 11), "imp-2"),                    # 25h later: outside 24h window
        ev("purchase", at(15, 10), "imp-3", raw_payload={"amount": 50}),  # within 7 days
    ])
    db.commit()
    aggregate_daily_metrics(db, date(2026, 11, 13))
    aggregate_daily_metrics(db, date(2026, 11, 14))

    r = rows(db)
    d13, d14 = r[date(2026, 11, 13)], r[date(2026, 11, 14)]
    assert (d13.impressions, d13.clicks) == (3, 3)
    assert d13.clicked_impressions == 1          # imp-1 once, despite 2 clicks
    assert d13.converted_impressions == 1        # imp-3 via purchase two days later
    assert d13.unattributed_clicks == 1          # ghost
    assert d14.clicks == 1 and d14.unattributed_clicks == 1   # outside window


def test_linked_ctr_never_exceeds_100(db):
    db.add(ev("impression", at(13, 10), "imp-1"))
    for m in range(5):
        db.add(ev("click", at(13, 10, 1 + m), "imp-1"))
    db.commit()
    aggregate_daily_metrics(db, date(2026, 11, 13))
    r = db.query(FactDailyMetrics).one()
    assert r.clicks == 5 and r.ctr == 500.0      # plain CTR is misleading here
    t = {k: getattr(r, k) for k in (
        "impressions", "clicks", "add_to_carts", "purchases", "revenue",
        "clicked_impressions", "converted_impressions",
        "unattributed_clicks", "unattributed_purchases")}
    assert derive(t)["linked_ctr"] == 100.0


def test_orphan_purchase_counted_unattributed(db):
    db.add(ev("purchase", at(13, 10), "ghost", raw_payload={"amount": 20}))
    db.commit()
    aggregate_daily_metrics(db, date(2026, 11, 13))
    r = db.query(FactDailyMetrics).one()
    assert r.purchases == 1 and r.unattributed_purchases == 1
    assert r.converted_impressions == 0