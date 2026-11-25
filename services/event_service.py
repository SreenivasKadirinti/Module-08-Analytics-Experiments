from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.tables import StagingEvent
from app.schemas.event import EventCreate


def create_event(db: Session, event_data: EventCreate):
    """
    Store an event. Idempotent on event_id.
    Returns (event, created): created=False means it was a duplicate.
    """
    if event_data.event_id:
        existing = (
            db.query(StagingEvent)
            .filter(StagingEvent.event_id == event_data.event_id)
            .first()
        )
        if existing:
            return existing, False

    db_event = StagingEvent(
        event_id=event_data.event_id,
        event_type=event_data.event_type,
        occurred_at=event_data.occurred_at,
        product_id=event_data.product_id,
        placement_id=event_data.placement_id,
        request_id=event_data.request_id,
        impression_id=event_data.impression_id,
        model_version=event_data.model_version,
        user_ref=event_data.user_ref,
        session_id=event_data.session_id,
        raw_payload=event_data.raw_payload,
    )
    db.add(db_event)
    try:
        db.commit()
    except IntegrityError:
        # Race: another request inserted the same event_id first
        db.rollback()
        existing = (
            db.query(StagingEvent)
            .filter(StagingEvent.event_id == event_data.event_id)
            .first()
        )
        if existing:
            return existing, False
        raise
    db.refresh(db_event)
    return db_event, True


def get_events(db: Session, limit: int = 20):
    return db.query(StagingEvent).order_by(StagingEvent.id.desc()).limit(limit).all()