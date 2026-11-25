import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from typing import List
from app.core.security import require_api_key
from app.database.connection import get_db
from app.schemas.event import EventCreate, EventResponse
from app.services.event_service import create_event, get_events
from app.core.auth import Role, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["Events"])


@router.post("/", response_model=EventResponse, status_code=201,
             dependencies=[Depends(require_role(Role.SERVICE))])
def add_event(event: EventCreate, response: Response, db: Session = Depends(get_db)):
    try:
        new_event, created = create_event(db, event)
    except Exception:
        db.rollback()
        logger.exception("Failed to store event")   # details go to the log, not the client
        raise HTTPException(status_code=500, detail="Failed to store event")
    if not created:
        response.status_code = 200  # duplicate: already stored
    return new_event


@router.get("/", response_model=List[EventResponse],
            dependencies=[Depends(require_role(Role.ADMIN))])
def list_events(limit: int = Query(20, ge=1, le=500), db: Session = Depends(get_db)):
    return get_events(db, limit)
