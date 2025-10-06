"""
Database initialization and management utilities.
"""

from loguru import logger
from sqlalchemy import text

from src.db.connection import engine
from src.db.models import Base


def drop_all_tables():
    """Drop all tables (use with caution!)."""
    logger.warning("Dropping all tables...")

    # First drop views created by schema.sql
    with engine.connect() as conn:
        logger.info("Dropping views...")
        conn.execute(text("DROP VIEW IF EXISTS active_vcs CASCADE"))
        conn.execute(text("DROP VIEW IF EXISTS people_enrichment_status CASCADE"))
        conn.commit()

    Base.metadata.drop_all(bind=engine)
    logger.info("All tables dropped")


def create_all_tables():
    """Create all tables from SQLAlchemy models."""
    logger.info("Creating all tables from SQLAlchemy models...")
    Base.metadata.create_all(bind=engine)
    logger.info("All tables created successfully")


def init_db(drop_existing: bool = False):
    """
    Initialize database.

    Args:
        drop_existing: If True, drop all existing tables first
    """
    if drop_existing:
        drop_all_tables()

    create_all_tables()

    # Create extensions
    with engine.connect() as conn:
        logger.info("Creating PostgreSQL extensions...")
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
        conn.commit()
        logger.info("Extensions created")

    logger.info("✅ Database initialized successfully")


def reset_db():
    """Drop and recreate all tables (destructive!)."""
    logger.warning("⚠️  Resetting database (all data will be lost)...")
    init_db(drop_existing=True)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        reset_db()
    else:
        init_db()
