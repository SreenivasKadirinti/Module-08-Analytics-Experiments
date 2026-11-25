from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import REVENUE_KEYS

MAX_CLOCK_SKEW = timedelta(minutes=5)


class EventCreate(BaseModel):
    event_id: Optional[str] = Field(None, max_length=100)
    event_type: Literal["impression", "click", "add_to_cart", "purchase"] = Field(
        ..., examples=["impression", "click", "add_to_cart", "purchase"]
    )
    occurred_at: datetime
    product_id: Optional[str] = Field(None, max_length=100)
    placement_id: Optional[str] = Field(None, max_length=100)
    request_id: Optional[str] = Field(None, max_length=100)
    impression_id: Optional[str] = Field(None, max_length=100)
    model_version: Optional[str] = Field(None, max_length=100)
    user_ref: Optional[str] = Field(None, max_length=100)
    session_id: Optional[str] = Field(None, max_length=100)
    raw_payload: Optional[Dict[str, Any]] = None

    @field_validator("event_type", mode="before")
    @classmethod
    def normalize_type(cls, v):
        # "Click " -> "click"; anything still invalid is rejected by the Literal
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator(
        "event_id", "product_id", "placement_id", "request_id",
        "impression_id", "model_version", "user_ref", "session_id",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @field_validator("occurred_at")
    @classmethod
    def to_utc_not_future(cls, v: datetime):
        if v.tzinfo is None:  # naive timestamps are treated as UTC
            v = v.replace(tzinfo=timezone.utc)
        v = v.astimezone(timezone.utc)
        if v > datetime.now(timezone.utc) + MAX_CLOCK_SKEW:
            raise ValueError("occurred_at cannot be in the future")
        return v

    @model_validator(mode="after")
    def purchase_needs_amount(self):
        if self.event_type == "purchase":
            payload = self.raw_payload or {}
            ok = False
            for key in REVENUE_KEYS:
                val = payload.get(key)
                if val is None:
                    continue
                try:
                    ok = float(val) >= 0
                except (TypeError, ValueError):
                    ok = False
                break
            if not ok:
                raise ValueError(
                    "purchase events need a non-negative amount in raw_payload "
                    f"(one of: {', '.join(REVENUE_KEYS)})"
                )
        return self


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: Optional[str]
    event_type: str
    occurred_at: datetime
    product_id: Optional[str]
    placement_id: Optional[str]
    request_id: Optional[str]
    impression_id: Optional[str]
    model_version: Optional[str]
    created_at: datetime