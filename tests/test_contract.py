from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.models.tables import FactDailyMetrics
from app.services.reports_service import freshness


def test_contract_paths_registered():
    paths = app.openapi()["paths"]
    for p in ("/api/v1/analytics/summary", "/api/v1/analytics/placements",
              "/api/v1/analytics/experiments", "/api/v1/analytics/metric-definitions",
              "/api/v1/analytics/export"):
        assert p in paths


def test_metric_definitions_are_public():
    r = TestClient(app).get("/api/v1/analytics/metric-definitions")
    assert r.status_code == 200
    body = r.json()
    assert "ctr" in body["metrics"] and body["known_limitations"]


def test_freshness_empty_then_filled(db):
    assert freshness(db) == {"last_aggregated_at": None, "latest_data_date": None}
    db.add(FactDailyMetrics(metric_date=date(2026, 11, 12), placement_id="p",
                            model_version="v", category_id="unknown"))
    db.commit()
    f = freshness(db)
    assert f["latest_data_date"] == "2026-11-12" and f["last_aggregated_at"]