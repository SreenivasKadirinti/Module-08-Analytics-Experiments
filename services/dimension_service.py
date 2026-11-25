from sqlalchemy.orm import Session
from app.models.tables import DimProduct, DimPlacement

def seed_products(db: Session):
    products = [
        DimProduct(product_id="PROD_1001", category_id="Electronics", brand_id="Sony", product_name="Sony Headphones", is_eligible=True),
        DimProduct(product_id="PROD_1002", category_id="Electronics", brand_id="Samsung", product_name="Samsung Earbuds", is_eligible=True),
        DimProduct(product_id="PROD_1003", category_id="Fashion", brand_id="Nike", product_name="Nike Running Shoes", is_eligible=True),
        DimProduct(product_id="PROD_1004", category_id="Home", brand_id="IKEA", product_name="Study Lamp", is_eligible=True),
        DimProduct(product_id="PROD_1005", category_id="Electronics", brand_id="Apple", product_name="AirPods Pro", is_eligible=True),
    ]
    
    for product in products:
        exists = db.query(DimProduct).filter(DimProduct.product_id == product.product_id).first()
        if not exists:
            db.add(product)
    
    db.commit()
    return {"message": "Products seeded successfully", "count": len(products)}

def seed_placements(db: Session):
    placements = [
        DimPlacement(placement_id="home_carousel", placement_name="Home Page Carousel", description="Main recommendation carousel on homepage", is_active=True),
        DimPlacement(placement_id="pdp_similar", placement_name="Product Page - Similar Items", description="Similar products on PDP", is_active=True),
        DimPlacement(placement_id="cart_recommend", placement_name="Cart Recommendations", description="Recommendations shown on cart page", is_active=True),
        DimPlacement(placement_id="search_sponsored", placement_name="Search Sponsored", description="Sponsored results in search", is_active=True),
    ]
    
    for placement in placements:
        exists = db.query(DimPlacement).filter(DimPlacement.placement_id == placement.placement_id).first()
        if not exists:
            db.add(placement)
    
    db.commit()
    return {"message": "Placements seeded successfully", "count": len(placements)}