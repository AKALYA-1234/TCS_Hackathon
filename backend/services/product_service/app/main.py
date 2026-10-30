from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from contextlib import asynccontextmanager

from common.database import engine, Base, get_db
from app.models import ProductModel
from app.schemas import ProductCreate, ProductResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-migrate tables on service boot
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(
    title="Product Microservice",
    version="1.0.0",
    description="Microservice responsible for Catalog & Inventory Management",
    lifespan=lifespan
)

@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(select(1))
        return {"status": "online", "service": "product_service", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "product_service", "database": str(e)}

@app.get("/products", response_model=List[ProductResponse])
async def list_products(category: str = None, skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)):
    query = select(ProductModel)
    if category:
        query = query.where(ProductModel.category == category)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@app.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(prod_in: ProductCreate, db: AsyncSession = Depends(get_db)):
    product = ProductModel(
        title=prod_in.title,
        price=prod_in.price,
        description=prod_in.description,
        category=prod_in.category or "General"
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product

@app.get("/products/{prod_id}", response_model=ProductResponse)
async def get_product(prod_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProductModel).where(ProductModel.id == prod_id))
    product = result.scalars().first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
