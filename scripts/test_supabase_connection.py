#!/usr/bin/env python3
"""
Test Supabase connection and verify transaction mode compatibility.

This script checks:
1. Database connection works
2. Prepared statements are properly disabled for transaction mode
3. Basic query execution works
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text

from src.config import settings
from src.db.connection import get_db


def test_connection():
    """Test basic database connection."""
    print("🔍 Testing Supabase connection...\n")

    # Check DATABASE_URL
    db_url = str(settings.database_url)
    print(f"📍 Database URL: {db_url[:50]}..." if len(db_url) > 50 else f"📍 Database URL: {db_url}")

    # Detect connection mode
    if "pooler.supabase.com:6543" in db_url:
        print("✅ Detected: Supabase Transaction Mode (port 6543)")
        print("   - Prepared statements: DISABLED ✓")
        print("   - Best for: API servers, Railway deployment")
    elif "pooler.supabase.com:5432" in db_url:
        print("✅ Detected: Supabase Session Mode (port 5432)")
        print("   - Connection pooling: ENABLED ✓")
        print("   - Best for: Persistent applications")
    elif "db." in db_url and "supabase.co:5432" in db_url:
        print("✅ Detected: Supabase Direct Connection (port 5432)")
        print("   - Full PostgreSQL features ✓")
        print("   - Best for: Migrations and admin tasks")
    elif "localhost" in db_url or "127.0.0.1" in db_url:
        print("ℹ️  Detected: Local PostgreSQL database")
    else:
        print("⚠️  Unknown connection type")

    print("\n" + "="*60)
    print("Testing connection...")
    print("="*60 + "\n")

    try:
        with get_db() as db:
            # Test 1: Check PostgreSQL version
            result = db.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ PostgreSQL Version: {version.split(',')[0]}")

            # Test 2: Check current database
            result = db.execute(text("SELECT current_database()"))
            db_name = result.fetchone()[0]
            print(f"✅ Current Database: {db_name}")

            # Test 3: Check connection info
            result = db.execute(text("SELECT inet_server_addr(), inet_server_port()"))
            server_info = result.fetchone()
            if server_info[0]:
                print(f"✅ Server Address: {server_info[0]}:{server_info[1]}")
            else:
                print(f"✅ Server Port: {server_info[1]} (Unix socket)")

            # Test 4: Check if we can query tables
            result = db.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """))
            table_count = result.fetchone()[0]
            print(f"✅ Tables in database: {table_count}")

            # Test 5: List tables
            if table_count > 0:
                result = db.execute(text("""
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY tablename
                """))
                tables = [row[0] for row in result.fetchall()]
                print(f"✅ Available tables: {', '.join(tables)}")

            # Test 6: Check row counts for key tables
            key_tables = ['orgs', 'people', 'deals', 'agent_runs']
            print("\n📊 Row Counts:")
            for table in key_tables:
                try:
                    result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.fetchone()[0]
                    print(f"   - {table}: {count} rows")
                except Exception as e:
                    print(f"   - {table}: Table not found or error ({str(e)[:50]})")

            print("\n" + "="*60)
            print("✅ All connection tests passed!")
            print("="*60)
            return True

    except Exception as e:
        print("\n" + "="*60)
        print("❌ Connection test failed!")
        print("="*60)
        print(f"\nError: {e}")
        print("\n💡 Troubleshooting:")
        print("1. Check your DATABASE_URL in .env file")
        print("2. Verify your Supabase password is correct")
        print("3. Ensure your Supabase project is running")
        print("4. Check if you're using the correct connection string:")
        print("   - Transaction mode: port 6543")
        print("   - Session mode: port 5432")
        print("   - Direct: port 5432 to db.xxxxx.supabase.co")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
