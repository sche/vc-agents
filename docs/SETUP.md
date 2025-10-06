# 🚀 VC Agents - Setup Guide

## Overview
This project provides an automated pipeline for crypto VC intelligence gathering, contact enrichment, and personalized outreach.

## Prerequisites

- **Python 3.11+** (required for latest LangGraph features)
- **PostgreSQL 14+**
- **Redis** (optional, recommended for production)
- **Node.js/npm** (for Playwright browser installation)

## Quick Start

### 1. Clone and Setup Environment

```bash
# Clone the repository
cd vc-agents

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -e ".[dev]"

# Install Playwright browsers
playwright install chromium
```

### 2. Database Setup

```bash
# Create PostgreSQL database
createdb vc_agents

# Run schema
psql vc_agents < db/schema.sql

# Or using psql directly
psql -U postgres -d vc_agents -f db/schema.sql
```

### 3. Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your preferred editor
```

**Required for MVP:**
- `DATABASE_URL` - Your PostgreSQL connection string
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` - For LLM-powered intro generation
- `NEYNAR_API_KEY` - For Farcaster enrichment (get from https://neynar.com)

**Optional but recommended:**
- `TWITTER_BEARER_TOKEN` - For Twitter enrichment
- `REDIS_URL` - For distributed rate limiting

### 4. Verify Installation

```bash
# Run tests
pytest

# Check database connection
python -c "from src.config import settings; print(settings.database_url)"

# Run type checking
mypy src/

# Format code
black src/
ruff check src/
```

## Project Structure

```
vc-agents/
├── db/
│   ├── schema.sql           # PostgreSQL schema
│   └── migrations/          # Alembic migrations (future)
├── src/
│   ├── config.py            # Configuration management
│   ├── db/                  # Database models & utilities
│   ├── agents/              # LangGraph agent implementations
│   │   ├── deals_ingestor.py
│   │   ├── vc_crawler.py
│   │   ├── social_enricher.py
│   │   └── intro_personalizer.py
│   ├── clients/             # External API clients
│   │   ├── defillama.py
│   │   ├── farcaster.py
│   │   └── twitter.py
│   ├── crawlers/            # Playwright-based crawlers
│   └── utils/               # Shared utilities
├── tests/                   # Test suite
├── prompts/                 # Prompt templates
├── docs/                    # Documentation
├── .env.example             # Example environment variables
├── pyproject.toml           # Project configuration
└── requirements.txt         # Python dependencies
```

## Development Workflow

### Running Agents

```bash
# Run deals ingestor
python -m src.agents.deals_ingestor --lookback-days 30

# Run VC crawler for specific org
python -m src.agents.vc_crawler --org-id <uuid>

# Run full pipeline
python -m src.run_pipeline
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/

# Run all checks
black src/ && ruff check src/ && mypy src/ && pytest
```

### Database Migrations (using Alembic - future)

```bash
# Create migration
alembic revision --autogenerate -m "Add new table"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## API Keys & Setup

### Neynar (Farcaster)
1. Sign up at https://neynar.com
2. Create an API key
3. Add to `.env`: `NEYNAR_API_KEY=your_key`

### Twitter API (Optional)
1. Apply for Twitter API access: https://developer.twitter.com
2. Create app and generate bearer token
3. Add to `.env`: `TWITTER_BEARER_TOKEN=your_token`

### DefiLlama
- No API key required for basic usage
- Rate limited to ~100 requests/hour
- Monitor at: https://defillama.com/docs/api

## Production Deployment

### Using Docker (recommended)

```bash
# Build image
docker build -t vc-agents .

# Run with docker-compose
docker-compose up -d
```

### Environment Variables in Production

Ensure these are set:
- `ENVIRONMENT=production`
- `LOG_LEVEL=INFO`
- `SENTRY_DSN=<your_sentry_dsn>` (optional but recommended)
- Secure `DATABASE_URL` with strong password
- Use Redis for rate limiting: `REDIS_URL=redis://...`

## Monitoring

### Database Queries

```sql
-- Check agent runs
SELECT agent_name, status, COUNT(*) 
FROM agent_runs 
WHERE started_at > NOW() - INTERVAL '24 hours'
GROUP BY agent_name, status;

-- Check enrichment progress
SELECT 
    (socials->>'farcaster' IS NOT NULL) as has_farcaster,
    (telegram_handle IS NOT NULL) as has_telegram,
    COUNT(*)
FROM people
GROUP BY has_farcaster, has_telegram;

-- Recent deals
SELECT * FROM deals ORDER BY announced_on DESC LIMIT 10;
```

### Logs

```bash
# View logs (if using systemd)
journalctl -u vc-agents -f

# Using Docker
docker logs -f vc-agents
```

## Troubleshooting

### Playwright Installation Issues

```bash
# Reinstall browsers
playwright install --force chromium

# Install system dependencies (Linux)
playwright install-deps
```

### Database Connection Issues

```bash
# Test connection
psql $DATABASE_URL

# Check PostgreSQL is running
pg_isready

# View active connections
psql -c "SELECT * FROM pg_stat_activity WHERE datname = 'vc_agents';"
```

### Import Errors

```bash
# Reinstall in development mode
pip install -e ".[dev]"

# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
```

## Next Steps

1. **Run your first agent**: Start with deals ingestor
2. **Review the data**: Check PostgreSQL tables
3. **Build custom agents**: See `agents/` directory for examples
4. **Set up monitoring**: Configure Sentry and logging
5. **Deploy**: Use Docker or your preferred deployment method

## Resources

- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [Playwright Python](https://playwright.dev/python/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [PostgreSQL JSONB](https://www.postgresql.org/docs/current/datatype-json.html)

## License

MIT

## Contributing

Pull requests welcome! Please run tests and formatting before submitting.
