from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.services.dimension_service import seed_products, seed_placements
from app.core.auth import Role, require_role

router = APIRouter(prefix="/dimensions", tags=["Dimensions"])

@router.post("/seed-products")
def seed_product_data(db: Session = Depends(get_db)):
    return seed_products(db)

@router.post("/seed-placements")
def seed_placement_data(db: Session = Depends(get_db)):
    return seed_placements(db)