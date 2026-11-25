import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.database.connection import engine
from app.routes import (
    aggregation, analytics, dimensions, events, experiment_assignment, reports, model_metrics
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="Analytics, Experimentation and Reporting APIs",
    version=settings.APP_VERSION,
)

# The dashboard only reads data (GET). Add your real frontend URL before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

for r in (events, dimensions, aggregation, analytics, reports):
    app.include_router(r.router, prefix="/api/v1")
app.include_router(analytics.public_router, prefix="/api/v1")
app.include_router(experiment_assignment.admin_router, prefix="/api/v1")
app.include_router(experiment_assignment.assign_router, prefix="/api/v1")
app.include_router(model_metrics.ingest_router, prefix="/api/v1")
app.include_router(model_metrics.read_router, prefix="/api/v1")


@app.get("/")
def home():
    return {
        "message": "Module 08 Analytics Backend is running",
        "status": "success",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health")
def health_check():
    return {
        "status": "UP",
        "module": "08 - Analytics, Experimentation & Reporting",
    }


@app.get("/db-check")
def db_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).fetchone()
        return {"database": "Connected successfully"}
    except Exception:
        logger.exception("Database check failed")   # details go to the log, not the client
        return {"database": "Connection failed"}