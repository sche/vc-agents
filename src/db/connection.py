"""Database connection setup with SQLAlchemy."""

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings

# Convert postgresql:// to postgresql+psycopg:// for psycopg3 compatibility
db_url = str(settings.database_url)
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)

# Async database URL (using asyncpg driver)
async_db_url = db_url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)

# Supabase Transaction Mode (port 6543) requires disabling prepared statements
# Check if using Supabase pooler on port 6543 (transaction mode)
connect_args = {}
if "pooler.supabase.com:6543" in db_url:
    # Disable prepared statements for Supabase transaction mode
    connect_args["prepare_threshold"] = None
    print("⚙️  Detected Supabase transaction mode - prepared statements disabled")

async_connect_args = {}
if "pooler.supabase.com:6543" in async_db_url:
    # For asyncpg, use statement_cache_size=0 to disable prepared statements
    async_connect_args["statement_cache_size"] = 0
    print("⚙️  Detected Supabase transaction mode (async) - statement cache disabled")

# Create engines
engine = create_engine(
    db_url,
    echo=False,
    pool_pre_ping=True,
    connect_args=connect_args
)
async_engine = create_async_engine(
    async_db_url,
    echo=False,
    pool_pre_ping=True,
    connect_args=async_connect_args
)

# Create session factories
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Usage:
        with get_db() as db:
            db.query(Organization).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@asynccontextmanager
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get async database session.

    Usage:
        async with get_async_db() as db:
            result = await db.execute(select(Organization))
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
