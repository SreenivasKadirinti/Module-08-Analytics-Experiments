# Module 08 – Analytics, Experimentation & Reporting
### Sprint 1 to Sprint 3 Only

**Project:** AI-Based Product Recommendation System  
**Module:** Analytics, Experimentation & Reporting (Employee Module 08)

---

## Scope of this Repository

This repository contains **only** the work completed up to **Sprint 3**.

| Sprint | Focus                              | Status     |
|--------|------------------------------------|------------|
| Sprint 1 | Metrics discovery & KPI glossary | Completed |
| Sprint 2 | Metric definitions & data model   | Completed |
| Sprint 3 | Summary query foundation          | Completed |

---

## Key Deliverables Included

- Metric definitions and KPI glossary (`core/metric_definitions.py`)
- Reporting data model / tables (`models/tables.py`)
- Aggregate & summary services (impressions, clicks, carts, purchases)
- Time filters and basic dimension support
- Unit / fixture tests for aggregation and summary logic

---

## Main Technical Files

- `core/metric_definitions.py` → Metric dictionary & denominators
- `models/tables.py` → Data model for reporting
- `services/aggregation_service.py` → Core aggregation logic (Sprint 3)
- `routes/analytics.py` & `routes/aggregation.py` → Summary APIs
- `tests/test_aggregation.py` & related tests

---

## How to Run (Basic)

1. Create virtual environment and install dependencies
2. Set required environment variables (see `.env.example` if available)
3. Run the application using the project’s standard command

---

## Note for Reviewer / Team Lead

This submission is limited to **Sprint 1 – Sprint 3** as requested.  
All experiment, model-metrics, export, and later dashboard features have been removed from this repository.