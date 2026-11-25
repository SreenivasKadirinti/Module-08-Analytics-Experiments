from sqlalchemy import (
    Column, BigInteger, String, Boolean, DateTime, Date,
    Integer, Float, Text, ForeignKey, Index
)
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.sql import func
from app.database.connection import Base
from sqlalchemy import UniqueConstraint

class StagingEvent(Base):
    """
    Stores raw behavioural events coming from Module 03
    (impressions, clicks, add-to-cart, purchases, etc.)
    """
    __tablename__ = "staging_events"
    __table_args__ = (
        Index(
            "uq_staging_events_event_id",
            "event_id",
            unique=True,
            postgresql_where=text("event_id IS NOT NULL"),
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(String(100), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)          # impression, click, add_to_cart, purchase
    occurred_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    
    product_id = Column(String(100), nullable=True, index=True)
    placement_id = Column(String(100), nullable=True, index=True)
    request_id = Column(String(100), nullable=True, index=True)
    impression_id = Column(String(100), nullable=True, index=True)
    model_version = Column(String(100), nullable=True, index=True)
    
    user_ref = Column(String(100), nullable=True)                        # pseudonymous user/session reference
    session_id = Column(String(100), nullable=True)
    
    raw_payload = Column(JSONB, nullable=True)                           # full original event for debugging
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<StagingEvent(id={self.id}, type={self.event_type})>"

class DimProduct(Base):
    """
    Product dimension table (from Module 02)
    """
    __tablename__ = "dim_product"

    product_id = Column(String(100), primary_key=True)
    category_id = Column(String(100), nullable=True, index=True)
    brand_id = Column(String(100), nullable=True, index=True)
    product_name = Column(String(255), nullable=True)
    is_eligible = Column(Boolean, default=True)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

class DimPlacement(Base):
    """
    Placement dimension (from Module 06)
    """
    __tablename__ = "dim_placement"

    placement_id = Column(String(100), primary_key=True)
    placement_name = Column(String(150), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

class FactDailyMetrics(Base):
    """
    Pre-aggregated daily metrics for fast dashboard queries.
    Grain: (metric_date, placement_id, model_version)
    """
    __tablename__ = "fact_daily_metrics"
    __table_args__ = (
        UniqueConstraint(
            "metric_date", "placement_id", "model_version", "category_id",
            name="uq_fact_daily_grain",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    metric_date = Column(Date, nullable=False, index=True)

    placement_id = Column(String(100), nullable=True, index=True)
    model_version = Column(String(100), nullable=True, index=True)
    category_id = Column(String(100), nullable=False, server_default="unknown", index=True)

    # Funnel counts
    impressions = Column(BigInteger, default=0)
    clicks = Column(BigInteger, default=0)
    add_to_carts = Column(BigInteger, default=0)
    purchases = Column(BigInteger, default=0)

    # Reach
    unique_users = Column(BigInteger, default=0)
    unique_sessions = Column(BigInteger, default=0)

    # Rates
    ctr = Column(Float, nullable=True)                      # clicks / impressions * 100
    atc_rate = Column(Float, nullable=True)                 # add_to_carts / clicks * 100
    conversion_rate = Column(Float, nullable=True)          # purchases / clicks * 100
    purchase_rate_from_atc = Column(Float, nullable=True)   # purchases / add_to_carts * 100

    # Revenue
    revenue = Column(Float, default=0.0)
    aov = Column(Float, nullable=True)                      # revenue / purchases
    revenue_per_impression = Column(Float, nullable=True)
    revenue_per_click = Column(Float, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Impression-linked funnel (cohort = impression date)
    clicked_impressions = Column(BigInteger, nullable=False, default=0, server_default="0")
    converted_impressions = Column(BigInteger, nullable=False, default=0, server_default="0")
    unattributed_clicks = Column(BigInteger, nullable=False, default=0, server_default="0")
    unattributed_purchases = Column(BigInteger, nullable=False, default=0, server_default="0")

class Experiment(Base):
    __tablename__ = "experiments"
    __table_args__ = (UniqueConstraint("key", name="uq_experiments_key"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key = Column(String(100), nullable=False)
    name = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, server_default="draft")   # draft | running | stopped
    variants = Column(JSONB, nullable=False)                              # [{"name": "A", "weight": 50}, ...]
    traffic_percent = Column(Integer, nullable=False, server_default="100")
    salt = Column(String(64), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    stopped_at = Column(TIMESTAMP(timezone=True), nullable=True)


class ExperimentExposure(Base):
    __tablename__ = "experiment_exposures"
    __table_args__ = (
        UniqueConstraint("experiment_key", "user_ref", name="uq_exposure_user"),
        Index("ix_exposures_experiment", "experiment_key"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    experiment_key = Column(String(100), nullable=False)
    user_ref = Column(String(100), nullable=False)
    variant = Column(String(50), nullable=False)
    exposed_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class ModelOfflineMetric(Base):
    __tablename__ = "model_offline_metrics"
    __table_args__ = (
        UniqueConstraint("model_version", "dataset_version", "metric_name", "k", "segment",
                         name="uq_offline_metric"),
        Index("ix_offline_model", "model_version"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_version = Column(String(100), nullable=False)
    dataset_version = Column(String(100), nullable=False)
    metric_name = Column(String(50), nullable=False)
    k = Column(Integer, nullable=False, server_default="0")          # 0 = not applicable
    segment = Column(String(30), nullable=False, server_default="all")   # all | cold_start | warm ...
    value = Column(Float, nullable=False)
    evaluated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())