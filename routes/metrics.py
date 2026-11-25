from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional

from app.database.connection import get_db
from app.services.metrics_service import get_basic_metrics, get_metrics_by_placement

router = APIRouter(prefix="/metrics", tags=["Metrics"])

@router.get("/summary")
def metrics_summary(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    placement_id: Optional[str] = Query(None, description="Filter by placement"),
    model_version: Optional[str] = Query(None, description="Filter by model version"),
    db: Session = Depends(get_db)
):
    return get_basic_metrics(
        db=db,
        start_date=start_date,
        end_date=end_date,
        placement_id=placement_id,
        model_version=model_version
    )

@router.get("/by-placement")
def metrics_by_placement(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    model_version: Optional[str] = Query(None, description="Filter by model version"),
    db: Session = Depends(get_db)
):
    return get_metrics_by_placement(
        db=db,
        start_date=start_date,
        end_date=end_date,
        model_version=model_version
    )