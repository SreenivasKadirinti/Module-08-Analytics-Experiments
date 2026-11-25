from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from app.schemas.event import EventCreate

T = "2026-11-13T10:00:00Z"

def make(**kw):
    base = {"event_type": "click", "occurred_at": T}
    base.update(kw)
    return EventCreate(**base)

def test_type_is_normalised():
    assert make(event_type="  Click ").event_type == "click"

@pytest.mark.parametrize("bad", ["clicks", "view", "", "purchased"])
def test_unknown_type_rejected(bad):
    with pytest.raises(ValidationError):
        make(event_type=bad)

def test_future_timestamp_rejected():
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    with pytest.raises(ValidationError):
        make(occurred_at=future)

def test_naive_timestamp_treated_as_utc():
    e = make(occurred_at="2026-11-13T10:00:00")
    assert e.occurred_at.tzinfo is not None
    assert e.occurred_at.utcoffset() == timedelta(0)

def test_offset_timestamp_converted_to_utc():
    e = make(occurred_at="2026-11-13T15:30:00+05:30")
    assert e.occurred_at == datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)

def test_blank_strings_become_none():
    assert make(user_ref="   ").user_ref is None

def test_purchase_requires_amount():
    with pytest.raises(ValidationError):
        make(event_type="purchase")
    with pytest.raises(ValidationError):
        make(event_type="purchase", raw_payload={"amount": "abc"})
    assert make(event_type="purchase", raw_payload={"amount": 89.25}).raw_payload["amount"] == 89.25