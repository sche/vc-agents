#!/usr/bin/env python3
"""
Quick verification script to check if the environment is set up correctly.
Run this after initial setup to verify everything works.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def check_python_version():
    """Check Python version is 3.11+"""
    print("🐍 Checking Python version...", end=" ")
    if sys.version_info >= (3, 11):
        print(f"{GREEN}✓ {sys.version.split()[0]}{RESET}")
        return True
    else:
        print(
            f"{RED}✗ Python 3.11+ required (found {sys.version.split()[0]}){RESET}")
        return False


def check_env_file():
    """Check if .env file exists"""
    print("📝 Checking .env file...", end=" ")
    if Path(".env").exists():
        print(f"{GREEN}✓ Found{RESET}")
        return True
    else:
        print(f"{YELLOW}⚠ Not found (copy .env.example to .env){RESET}")
        return False


def check_dependencies():
    """Check if key dependencies are installed"""
    print("📦 Checking dependencies...", end=" ")
    missing = []

    try:
        import langgraph
    except ImportError:
        missing.append("langgraph")

    try:
        import sqlalchemy
    except ImportError:
        missing.append("sqlalchemy")

    try:
        import playwright
    except ImportError:
        missing.append("playwright")

    try:
        import pydantic
    except ImportError:
        missing.append("pydantic")

    if not missing:
        print(f"{GREEN}✓ All installed{RESET}")
        return True
    else:
        print(f"{RED}✗ Missing: {', '.join(missing)}{RESET}")
        print(f"  Run: {YELLOW}make install-dev{RESET}")
        return False


def check_database_connection():
    """Check database connection"""
    print("🗄️  Checking database connection...", end=" ")

    try:
        from sqlalchemy import create_engine, text

        from src.config import settings

        # Use psycopg3 driver
        database_url = str(settings.database_url)
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

        engine = create_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.commit()

        print(f"{GREEN}✓ Connected{RESET}")
        return True
    except ImportError as e:
        print(f"{YELLOW}⚠ Import error: {e}{RESET}")
        return False
    except Exception as e:
        print(f"{RED}✗ Failed: {str(e)}{RESET}")
        print(f"  Check DATABASE_URL in .env")
        return False
def check_database_schema():
    """Check if database tables exist"""
    print("📊 Checking database schema...", end=" ")

    try:
        from sqlalchemy import create_engine, inspect

        from src.config import settings

        # Use psycopg3 driver
        database_url = str(settings.database_url)
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

        engine = create_engine(database_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        expected_tables = ["orgs", "deals", "people",
                           "roles_employment", "evidence", "intros", "agent_runs"]
        missing_tables = [t for t in expected_tables if t not in tables]

        if not missing_tables:
            print(f"{GREEN}✓ All tables present{RESET}")
            return True
        else:
            print(f"{YELLOW}⚠ Missing tables: {', '.join(missing_tables)}{RESET}")
            print(f"  Run: {YELLOW}make db-schema{RESET}")
            return False
    except ImportError:
        print(f"{YELLOW}⚠ Skipped (dependencies not installed){RESET}")
        return False
    except Exception as e:
        print(f"{YELLOW}⚠ Could not check: {str(e)}{RESET}")
        return False


def check_api_keys():
    """Check if API keys are configured"""
    print("🔑 Checking API keys...", end=" ")

    try:
        from src.config import settings

        has_llm = bool(settings.openai_api_key or settings.anthropic_api_key)
        has_farcaster = bool(settings.neynar_api_key)

        if has_llm:
            print(f"{GREEN}✓ LLM API key configured{RESET}")
        else:
            print(
                f"{YELLOW}⚠ No LLM API key (set OPENAI_API_KEY or ANTHROPIC_API_KEY){RESET}")

        if has_farcaster:
            print(f"  {GREEN}✓ Farcaster API key configured{RESET}")
        else:
            print(f"  {YELLOW}⚠ No Farcaster API key (optional){RESET}")

        return has_llm
    except ImportError:
        print(f"{YELLOW}⚠ Skipped (dependencies not installed){RESET}")
        return False
    except Exception as e:
        print(f"{YELLOW}⚠ Could not check: {str(e)}{RESET}")
        return False


def main():
    """Run all checks"""
    print("\n" + "=" * 60)
    print("  VC-Agents Environment Verification")
    print("=" * 60 + "\n")

    results = []

    results.append(check_python_version())
    results.append(check_env_file())
    results.append(check_dependencies())

    # Only check database if dependencies are installed
    if results[-1]:  # If dependencies check passed
        results.append(check_database_connection())
        results.append(check_database_schema())
        results.append(check_api_keys())

    print("\n" + "=" * 60)

    if all(results):
        print(f"{GREEN}✅ All checks passed! Environment is ready.{RESET}")
        print(f"\nNext steps:")
        print(f"  1. Review your .env configuration")
        print(f"  2. Run tests: {YELLOW}make test{RESET}")
        print(f"  3. Start building agents!")
    else:
        print(f"{YELLOW}⚠️  Some checks failed. Review the output above.{RESET}")
        print(f"\nQuick fixes:")
        print(f"  - Install dependencies: {YELLOW}make install-dev{RESET}")
        print(
            f"  - Setup database: {YELLOW}make db-create && make db-schema{RESET}")
        print(
            f"  - Configure .env: {YELLOW}cp .env.example .env{RESET} and edit")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
