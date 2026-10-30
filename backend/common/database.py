import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

# Default to pre-seeded SQLite app.db if DATABASE_URL is not set or points to timescaledb in local run
default_sqlite = f"sqlite+aiosqlite:///{os.path.abspath(os.path.join(os.path.dirname(__file__), '../../app.db'))}"
DATABASE_URL = os.getenv("DATABASE_URL") or default_sqlite

# Engine configuration depending on dialect
if "sqlite" in DATABASE_URL:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True
    )
else:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        pool_size=10,
        max_overflow=20
    )

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def initialize_timescale():
    """Ensure TimescaleDB extension is active and hypertable is registered if on PostgreSQL."""
    if "sqlite" in DATABASE_URL:
        return
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
    except Exception as e:
        print(f"TimescaleDB extension check: {e}")
