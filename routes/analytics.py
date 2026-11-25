import logging
from datetime import date
from typing import Optional
from app.core.metric_definitions import METRIC_DEFINITIONS

from app.models.tables import Experiment

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from app.core.auth import Principal, Role, require_role

from app.database.connection import get_db
from app.routes.reports import Metric, _range, _run
from app.services import reports_service as svc
from app.services.experiment_service import compare_models
from app.services.export_service import ExportTooLarge, build_export
from app.services.ab_service import Conflict, NotFound, experiment_results

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["Analytics"],
                   dependencies=[Depends(require_role(Role.ANALYST))])
public_router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary")
def summary(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    placement_id: Optional[str] = Query(None),
    model_version: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    s, e = _range(start_date, end_date)
    flt = dict(placement_id=placement_id, model_version=model_version, category_id=category_id)
    return {
        "period": {"start_date": str(s), "end_date": str(e)},
        "filters": flt,
        "metrics": _run(svc.totals, db, s, e, **flt),
        "freshness": _run(svc.freshness, db),
        "definitions": "/api/v1/analytics/metric-definitions",
    }


@router.get("/placements")
def placements(
    sort_by: Metric = Query("impressions"),
    limit: int = Query(20, ge=1, le=100),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    model_version: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    s, e = _range(start_date, end_date)
    out = _run(svc.breakdown, db, s, e, "placement_id", sort_by, limit,
               model_version=model_version, category_id=category_id)
    out["freshness"] = _run(svc.freshness, db)
    return out


@router.get("/experiments")
def experiments(
    model_a: str = Query(...),
    model_b: str = Query(...),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    placement_id: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    min_sample: int = Query(100, ge=1),
    alpha: float = Query(0.05, gt=0, lt=1),
    db: Session = Depends(get_db),
):
    if model_a == model_b:
        raise HTTPException(400, "model_a and model_b must differ")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(400, "start_date must be on or before end_date")
    try:
        result, missing = compare_models(db, model_a, model_b, start_date, end_date,
                            placement_id, category_id, min_sample, alpha)
    except Exception:
        db.rollback()
        logger.exception("Experiment comparison failed")
        raise HTTPException(500, "Comparison failed")
    if missing:
        raise HTTPException(404, f"No aggregated data for model_version: {', '.join(missing)} in this range")
    return result


@public_router.get("/metric-definitions")
def metric_definitions():
    return METRIC_DEFINITIONS


@router.get("/export")
def export_csv(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    placement_id: Optional[str] = Query(None),
    model_version: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    who: Principal = Depends(require_role(Role.ANALYST)),
):
    s, e = _range(start_date, end_date)
    try:
        body = build_export(db, s, e, placement_id=placement_id,
                            model_version=model_version, category_id=category_id)
    except ExportTooLarge as ex:
        raise HTTPException(400, str(ex))
    except Exception:
        db.rollback()
        logger.exception("Export failed")
        raise HTTPException(500, "Export failed")
    logger.info("export by %s (%s): %s..%s", who.subject, who.role.value, s, e)  # no data, no user ids
    return Response(
        content=body, media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="analytics_{s}_{e}.csv"'},
    )


@router.get("/experiments/{key}/results")
def experiment_result(
    key: str,
    min_sample: int = Query(100, ge=1),
    alpha: float = Query(0.05, gt=0, lt=1),
    db: Session = Depends(get_db),
):
    try:
        return experiment_results(db, key, min_sample, alpha)
    except NotFound as e:
        raise HTTPException(404, str(e))
    except Exception:
        db.rollback()
        logger.exception("Experiment results failed")
        raise HTTPException(500, "Experiment results failed")

@router.get("/experiment-list")
def experiment_list(db: Session = Depends(get_db)):
    rows = db.query(Experiment).order_by(Experiment.id.desc()).limit(100).all()
    return [
        {"key": r.key, "name": r.name, "status": r.status,
         "started_at": r.started_at.isoformat() if r.started_at else None,
         "stopped_at": r.stopped_at.isoformat() if r.stopped_at else None}
        for r in rows
    ]