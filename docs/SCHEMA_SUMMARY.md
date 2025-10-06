# Database & Dependencies Setup - Summary

## ✅ What We've Created

### 1. **Database Schema** (`db/schema.sql`)

A comprehensive PostgreSQL schema with:

- **8 Core Tables:**
  - `orgs` - VCs, startups, accelerators
  - `deals` - Funding rounds with idempotency
  - `people` - Contact information
  - `roles_employment` - Who works where (with history)
  - `evidence` - Audit trail of all scraped data
  - `intros` - Generated outreach messages
  - `agent_runs` - Execution tracking
  - `rate_limits` - Simple rate limiting without Redis

- **Key Features:**
  - JSONB columns for flexible data (`socials`, `sources`, `focus`, etc.)
  - Idempotency via `uniq_hash` and `uniq_key` fields
  - Full audit trail with `created_at`, `updated_at`
  - GIN indexes on JSONB columns for fast queries
  - Auto-update triggers for `updated_at` timestamps
  - Helpful views: `active_vcs`, `people_enrichment_status`

### 2. **Python Dependencies**

**Core Stack:**
- `langgraph` - Agent orchestration
- `langchain` + OpenAI/Anthropic - LLM integration
- `sqlalchemy` + `psycopg` - Database ORM
- `playwright` - Web scraping
- `pydantic` + `pydantic-settings` - Configuration & validation

**Full list:** See `requirements.txt` and `pyproject.toml`

### 3. **Project Configuration**

**`pyproject.toml`:**
- Project metadata & dependencies
- Tool configuration (black, ruff, mypy, pytest)
- Development/monitoring/api optional dependencies

**`src/config.py`:**
- Pydantic-based settings management
- Environment variable loading from `.env`
- Type-safe configuration with validation
- Convenience properties (`is_production`, `has_twitter_api`, etc.)

**`.env.example`:**
- Template for all required environment variables
- Organized by category (DB, APIs, Crawler, Monitoring)

### 4. **Database Utilities**

**`src/db/connection.py`:**
- Synchronous & async database sessions
- Context managers for safe connection handling
- Connection pooling configuration

**`src/utils/helpers.py`:**
- URL/name normalization functions
- Hash generation for idempotency
- Currency conversion utilities
- Text cleaning & parsing helpers

### 5. **Development Tools**

**`Makefile`:**
- Quick commands for common tasks
- Database operations (create, schema, reset)
- Code quality (lint, format, test)
- Agent execution shortcuts

**`.gitignore`:**
- Ignore Python cache, virtual envs, secrets, etc.

**`docs/SETUP.md`:**
- Complete setup instructions
- Troubleshooting guide
- Development workflow

## 🎯 Recommended Stack - Final Decision

Based on your long-term goals (sophisticated AI agents with memory):

✅ **LangGraph** - For agent orchestration (learning investment)  
✅ **PostgreSQL** - Source of truth with JSONB support  
✅ **Redis** - Optional for MVP, recommended for production  
✅ **Playwright** - Modern web scraping  
✅ **Python 3.11+** - Latest features

## 📋 Next Steps

### Immediate (Ready to Code)

1. **Set up environment:**
   ```bash
   make setup
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. **Verify installation:**
   ```bash
   make test
   make lint
   ```

3. **Check database:**
   ```bash
   psql vc_agents -c "\dt"  # List tables
   ```

### Next Session - Build First Agent

We should start with the **Deals Ingestor** agent because:
- Simplest workflow (API call → normalize → insert)
- Populates foundational data (orgs & deals)
- Good LangGraph learning starting point
- No dependencies on other agents

**Deals Ingestor will:**
1. Fetch recent crypto raises from DefiLlama
2. Normalize currency to EUR
3. Generate `uniq_hash` for idempotency
4. Upsert orgs (startups + VCs)
5. Insert deals
6. Log execution in `agent_runs`

### Future Sessions

1. **VC Crawler** - Scrape team pages
2. **Social Enricher** - Find Farcaster/Twitter/Telegram
3. **Intro Personalizer** - Generate outreach messages
4. **Pipeline Orchestration** - Connect all agents

## 🔑 Key Design Decisions

### Why JSONB?
- Flexible schema for evolving data (new social platforms, etc.)
- Fast queries with GIN indexes
- Native PostgreSQL type (no ORM complexity)

### Why Idempotency Keys?
- Safe to re-run agents without duplicates
- `uniq_hash` for deals: same deal won't be inserted twice
- `uniq_key` for orgs/people: deduplication across sources

### Why Evidence Table?
- Audit trail for compliance
- Debug data quality issues
- Reconstruct how data was obtained
- Screenshot/HTML snapshots for manual review

### Why Rate Limits Table?
- MVP can work without Redis
- Simpler deployment
- Upgrade to Redis later for distributed systems

## 📚 Schema Highlights

### Example: Upserting an Org

```python
from src.utils.helpers import generate_org_uniq_key

uniq_key = generate_org_uniq_key("Paradigm", "https://paradigm.xyz")

# SQL with ON CONFLICT
INSERT INTO orgs (name, kind, website, uniq_key, sources)
VALUES ('Paradigm', 'vc', 'https://paradigm.xyz', uniq_key, '[{"type": "defillama"}]')
ON CONFLICT (uniq_key) DO UPDATE SET
    updated_at = NOW(),
    sources = orgs.sources || EXCLUDED.sources;
```

### Example: JSONB Queries

```sql
-- Find VCs with DeFi focus
SELECT * FROM orgs 
WHERE kind = 'vc' AND focus @> '["DeFi"]';

-- Find people with Farcaster
SELECT * FROM people 
WHERE socials->>'farcaster' IS NOT NULL;

-- Find deals from specific investor
SELECT * FROM deals 
WHERE investors @> '["a16z"]';
```

## 🚨 Important Notes

- **No dependencies installed yet** - Run `make install-dev` first
- **PostgreSQL must be running** - Check with `pg_isready`
- **Python 3.11+ required** - LangGraph needs modern Python
- **API keys needed** - At minimum: OpenAI/Anthropic + Neynar

## Questions Before Next Session?

1. Do you want to set up the environment now or in the next session?
2. Should we add Docker setup for easier deployment?
3. Any other tables/fields you think we need?
4. Ready to start building the first agent (Deals Ingestor)?

---

**Status:** ✅ Schema & dependencies ready  
**Next:** Build Deals Ingestor agent with LangGraph
