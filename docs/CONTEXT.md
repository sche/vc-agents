# Project Context: VC Network Intel (1‑week MVP)


## Goal
End‑to‑end pipeline to (1) fetch crypto VC deals, (2) crawl VC sites for team members, (3) enrich contacts with socials (Farcaster, X/Twitter; infer Telegram handle), and (4) generate a short personalized intro message for each target contact.


## Current Status (Updated: Oct 8, 2025 - Evening)
✅ **Completed:**
- Database architecture: Full SQLAlchemy 2.0 ORM models (8 tables)
- Database management: Pure Python init/reset via SQLAlchemy (no SQL files)
- Deal loader: 208 crypto deals loaded from DefiLlama (10 startups, 21 VCs extracted)
- VC extraction: Automatically creates VC orgs from deal investor lists
- **VC Crawler Agent**: Production-ready with intelligent team page discovery
  - OpenAI GPT-4o-mini for data extraction
  - Smart time-based refresh (30-day default, configurable)
  - Full URL storage (profile_url, headshot_url)
  - Evidence tracking with screenshots
  - Stats: 26 people extracted from Paradigm VC
- Test VCs added: Andreessen Horowitz, Sequoia, Paradigm, Multicoin, Pantera

⏳ **In Progress:**
- Testing VC crawler on all 5 test VCs

🔜 **Next Steps:**
- Build social enricher agent (Farcaster, X/Twitter)
- Build intro generator agent
- Create Retool/Airtable UI (postponed - requires license)


## Outcomes (by EOW)
- Postgres DB with orgs/people/deals/evidence/intros tables ✅
- 3 automated pipelines + intro generator ⏳
- Retool/Airtable as ops UI for review/edits 🔜


## High‑level architecture
- **Orchestrator:** LangGraph (Python) for complex workflows with decision trees. Simple scripts for straightforward ETL.
- **DB:** Postgres (source of truth) managed via SQLAlchemy 2.0 ORM. No raw SQL files.
- **Queue/Cache:** Redis (rate limit buckets, retries, dedup) - optional, using DB-based rate limiting for MVP.
- **Crawling:** Playwright (headless). Respect robots.txt & ToS.
- **APIs:** DefiLlama (fundraising data ✅); Farcaster via Neynar; X/Twitter if token available. Telegram handle **inference only** for MVP.
- **UI:** Retool or Airtable views on top of Postgres (read/write for text fields).



## Data model (essentials)

**SQLAlchemy 2.0 ORM Models (Modern syntax with `Mapped` types):**

- **orgs**: Organizations (VCs, startups, accelerators, other)
  - Fields: id (UUID), name, kind ('vc'|'startup'|'accelerator'|'other'), website, description, focus (JSONB), location (JSONB), sources (JSONB), socials (JSONB), uniq_key (SHA256), created_at, updated_at
  - Relationships: deals[], roles[]
  - Deduplication: uniq_key = SHA256(normalized_name + normalized_website)
  - Constraint: UniqueConstraint(name, kind)

- **deals**: Funding rounds with normalized USD amounts
  - Fields: id (UUID), org_id (FK), round, amount_usd (Numeric), amount_original, currency_original, announced_on (Date), investors (JSONB list), source (JSONB), uniq_hash (SHA256), created_at, updated_at
  - Relationships: organization
  - Deduplication: uniq_hash = SHA256(org_name + date + round + amount)
  - Note: Previously had amount_eur but fixed to amount_usd (Oct 2025)

- **people**: Individual contacts (VC partners, team members)
  - Fields: id (UUID), full_name, email, socials (JSONB), telegram_handle, telegram_confidence (0-1), discovered_from (JSONB), enrichment_history (JSONB), uniq_key (SHA256), created_at, updated_at
  - Relationships: roles[], intros[]

- **roles_employment**: Who works where (many-to-many with history)
  - Fields: id (UUID), person_id (FK), org_id (FK), title, seniority, start_date, end_date, is_current (bool), evidence_id (FK), created_at, updated_at
  - Constraint: UniqueConstraint(person_id, org_id, title, is_current)

- **evidence**: Audit trail of all scraped/fetched data
  - Fields: id (UUID), evidence_type, url, selector, raw_html, raw_json (JSONB), screenshot_url, extracted_data (JSONB), extraction_method, org_id, person_id, created_at

- **intros**: Generated outreach messages
  - Fields: id (UUID), person_id (FK), message (Text), subject, context_snapshot (JSONB), status ('draft'|'sent'|etc), sent_at, sent_via, reviewed_by, review_notes, created_at, updated_at

- **agent_runs**: Execution logs for LangGraph agents
  - Fields: id (UUID), agent_name, status, input_params (JSONB), output_summary (JSONB), started_at, completed_at, error_message, error_trace, langgraph_state (JSONB)

- **rate_limits**: DB-based rate limiting (alternative to Redis for MVP)
  - Fields: id (UUID), service, identifier, window_start, window_duration_seconds, request_count, max_requests, last_request_at
  - Constraint: UniqueConstraint(service, identifier, window_start)


## Implementation Details

**Database Management:**
- Pure Python via SQLAlchemy 2.0 (no SQL files)
- `src/db/init_db.py`: drop_all_tables(), create_all_tables(), init_db(), reset_db()
- CLI: `python -m src.db.init_db [--reset]`
- Makefile targets: `make db-init`, `make db-reset`

**ETL Pipeline:**
- `scripts/load_defillama_deals.py`: Simple 200-line script (not LangGraph)
- Loads 208 deals from DefiLlama API (90-day lookback)
- Creates/updates startup organizations
- Extracts and creates VC organizations from investor lists
- Idempotent via uniq_hash for deals, uniq_key for orgs
- Stats: 195 deals loaded, 13 skipped (no amount), 201 orgs created
- CLI: `python scripts/load_defillama_deals.py [--since-days 90] [--limit N]`
- Makefile: `make load-deals`

**Hash-Based Deduplication:**
- `src/utils/helpers.py`: generate_org_uniq_key(), generate_deal_uniq_hash()
- Org: SHA256(normalized_name + normalized_website)
- Deal: SHA256(normalized_name + date + round + amount)
- Name normalization: lowercase, remove special chars, strip legal suffixes
- URL normalization: lowercase, remove www., strip query params


## Agents (ownership & responsibilities)

**Implemented:**
1. ✅ **Deals Ingestor** — Fetch raises from DefiLlama, normalize startups/investors, idempotent upserts. Simple script (not LangGraph).
2. ✅ **VC Extractor** — Extract VC organizations from deal investor lists, create org records with kind='vc'. Built into deals loader.
3. ✅ **VC Crawler** — Discover team pages, extract (name, title, profile URL), store evidence. Uses OpenAI GPT-4o-mini + Playwright.
   - **Features**: Smart navigation (common paths + LLM analysis), full URL storage, time-based refresh (30-day default)
   - **CLI**: `python -m src.agents.vc_crawler [--limit N] [--vc-name "Name"] [--force-refresh]`
   - **Stats tracking**: created/updated/skipped counts with enrichment history
   - **Evidence**: Screenshots + extracted data with confidence scores

**In Development:**
4. ⏳ **Social Enricher** — Find Farcaster & X/Twitter; infer Telegram handle; set confidence. LangGraph workflow.

**Planned:**
5. 🔜 **Intro Personalizer** — Generate 2 variants of short outreach copy; store to `intros`. LangGraph workflow.

**Architecture Decision:**
- **Simple ETL tasks** → Python scripts (e.g., load_defillama_deals.py)
- **Complex decision workflows** → LangGraph (e.g., crawler navigation, social enrichment logic)
- Rationale: Use the right tool for the job. Scripts are easier to debug and maintain for straightforward data loading.



## Concurrency & safety

- Idempotent DB writes (upserts by `uniq_hash`/natural keys + versioning if needed)
- Rate limits and polite crawling; exponential backoff with jitter
- Provenance: always persist `source` (url, ts, extractor) in `evidence`
- ToS guardrails: **no LinkedIn scraping in MVP**; Telegram: do not read messages


## High-level plan

- ✅ **Day 1-2**: Repo + SQLAlchemy ORM; database init; Makefile
- ✅ **Day 3**: Deals ingestor (DefiLlama); first rows in `orgs/deals`
- ⏳ **Day 4**: VC extraction from investors; crawler for team pages
- 🔜 **Day 5**: Social enrichment; Telegram inference
- 🔜 **Day 6**: Intro generation; storage + review screen
- 🔜 **Day 7**: Glue (retries, schedules); QA; CSV export; README


## Key Learnings & Decisions

1. **SQLAlchemy > Raw SQL**: Eliminated all SQL files, pure Python ORM approach
2. **Script vs Agent**: Use simple scripts for ETL, LangGraph for complex workflows
3. **Currency Fix**: DefiLlama amounts are USD, not EUR (fixed Oct 2025)
4. **VC Extraction**: Create separate VC orgs from investor lists, not just store as strings
5. **VC Extraction**: Create separate VC orgs from investor lists, not just store as strings
6. **Session Management**: Capture IDs before session.close() to avoid detachment errors
7. **None Handling**: Explicit None checks before type conversion (e.g., float(amount))
8. **Time-Based Refresh**: Skip updates for recently crawled data (30-day default) to save API costs
9. **Full URLs**: Always store complete URLs with domain, not relative paths
10. **Evidence Trail**: Store extraction method, confidence scores, and screenshots for all crawled data


## Prompts & tone

- Respectful, concise, 2–3 sentences; avoid scraping claims; state value + light CTA
