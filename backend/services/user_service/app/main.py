from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from contextlib import asynccontextmanager

from common.database import engine, Base, get_db
from app.models import UserModel
from app.schemas import UserCreate, UserResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-migrate tables on service boot
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(
    title="User Microservice",
    version="1.0.0",
    description="Microservice responsible for User Account & Identity Domain",
    lifespan=lifespan
)

@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        # Check DB connection
        await db.execute(select(1))
        return {"status": "online", "service": "user_service", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "user_service", "database": str(e)}

@app.get("/users", response_model=List[UserResponse])
async def list_users(skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserModel).offset(skip).limit(limit))
    return result.scalars().all()

@app.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if username or email already exists
    existing = await db.execute(
        select(UserModel).where((UserModel.username == user_in.username) | (UserModel.email == user_in.email))
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Username or email already exists."
        )

    user = UserModel(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
