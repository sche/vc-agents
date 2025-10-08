# 🚀 VC Agents

AI-powered intelligence pipeline for crypto VC deal sourcing and outreach.

## 📖 Overview

This project automates the end-to-end process of:
1. 📊 **Fetching crypto VC deals** from public sources (DefiLlama)
2. 🕷️ **Crawling VC websites** to discover team members
3. 🔍 **Enriching contacts** with social profiles (Farcaster, Twitter, Telegram)
4. ✉️ **Generating personalized intros** for outreach

Built with **LangGraph** for sophisticated agent workflows and **PostgreSQL** for robust data storage.

## 🛠️ Tech Stack

- **LangGraph** - Agent orchestration with state management
- **PostgreSQL** - Source of truth with JSONB support
- **Playwright** - Modern web scraping
- **Pydantic** - Type-safe configuration
- **Python 3.11+** - Latest language features

## ⚡ Quick Start

```bash
# 1. Install dependencies
make install-dev

# 2. Set up database
make db-create db-schema

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 4. Verify setup
make verify

# 5. Run first agent
make run-deals
```

## 🚀 Deployment & Production

### Cloud Deployment

Deploy the API and database to the cloud:

**Stack:**
- **Database**: [Supabase](https://supabase.com) - Managed PostgreSQL (free tier available)
- **API Server**: [Railway](https://railway.app) - Auto-deploy from GitHub (~$5-10/month)

**Quick Deploy:**

```bash
# 1. Deploy database to Supabase
# - Create project at supabase.com
# - Copy connection string

# 2. Deploy API to Railway
# - Connect GitHub repo (supports private repos)
# - Railway will auto-detect configuration
# - Add environment variables (see Railway guide)

# 3. Initialize database schema
railway run python -m src.db.init_db
```

**Documentation:**
- [Railway Deployment Guide](docs/RAILWAY_DEPLOYMENT.md) - Step-by-step deployment to Railway
- [Retool API Integration](docs/RETOOL_API.md) - Retool Cloud setup guide
- [Retool Triggers Quick Start](docs/RETOOL_TRIGGERS.md) - Trigger agents from Retool Cloud UI

### Local API Server
```

## � Deployment & Production

### Cloud Deployment (Recommended for Retool Integration)

Deploy the API and database to the cloud for integration with Retool:

**Stack:**
- **Database**: [Supabase](https://supabase.com) - Managed PostgreSQL (free tier available)
- **API Server**: [Railway](https://railway.app) - Auto-deploy from GitHub (~$5-10/month)
- **Frontend**: [Retool](https://retool.com) - Low-code dashboard for agent orchestration

**Quick Deploy:**

```bash
# 1. Deploy database to Supabase
# - Create project at supabase.com
# - Copy connection string

# 2. Deploy API to Railway
# - Connect GitHub repo (supports private repos)
# - Railway will auto-detect configuration
# - Add environment variables (see Railway guide)

# 3. Initialize database schema
railway run python -m src.db.init_db

# 4. Connect Retool
# - Add REST API resource (Railway URL)
# - Add PostgreSQL resource (Supabase)
# - Import dashboard template
```

**Documentation:**
- [Railway Deployment Guide](docs/RAILWAY_DEPLOYMENT.md) - Step-by-step deployment to Railway
- [Retool API Integration](docs/RETOOL_API.md) - Complete Retool setup guide
- [Retool Triggers Quick Start](docs/RETOOL_TRIGGERS.md) - Trigger agents from Retool UI

### Local API Server

Run the FastAPI server locally for development:

```bash
make run-api
# Access at http://localhost:8000/docs
```

## 📚 Documentation
```

## �📚 Documentation

- [**Setup Guide**](docs/SETUP.md) - Detailed installation and configuration
- [**Schema Summary**](docs/SCHEMA_SUMMARY.md) - Database design and decisions
- [**Context**](docs/CONTEXT.md) - Project goals and architecture

## 🗂️ Project Structure

```
vc-agents/
├── agents/              # Agent specifications (markdown)
├── db/                  # Database schema and migrations
├── docs/                # Documentation
├── prompts/             # LLM prompt templates
├── scripts/             # Utility scripts
├── src/
│   ├── agents/          # LangGraph agent implementations
│   ├── clients/         # External API clients
│   ├── crawlers/        # Web scraping logic
│   ├── db/              # Database utilities
│   └── utils/           # Shared helpers
└── tests/               # Test suite
```

## 🎯 Agents

### 1. Deals Ingestor
Fetches recent crypto raises and populates `orgs` and `deals` tables.

### 2. VC Crawler
Discovers team members from VC websites using Playwright.

### 3. Social Enricher
Finds Farcaster, Twitter, and infers Telegram handles with confidence scoring.

### 4. Intro Personalizer
Generates contextual, respectful outreach messages.

## 🔑 Required API Keys

- **OpenAI or Anthropic** - For LLM-powered intro generation
- **Neynar** - For Farcaster enrichment (get from [neynar.com](https://neynar.com))
- **Twitter API** - Optional, for Twitter enrichment

## 📊 Database Schema

Key tables:
- `orgs` - VCs, startups, accelerators
- `deals` - Funding rounds with idempotency
- `people` - Contact information with social profiles
- `roles_employment` - Employment history
- `evidence` - Audit trail of all scraped data
- `intros` - Generated outreach messages
- `agent_runs` - Execution tracking

See [Schema Summary](docs/SCHEMA_SUMMARY.md) for details.

## 🧪 Development

```bash
# Run tests
make test

# Code formatting
make format

# Linting
make lint

# All checks
make check
```

## 📝 License

MIT

## 🤝 Contributing

This is a learning project for exploring LangGraph and agentic workflows. Feel free to explore and experiment!

---

Below are ready‑to‑paste files. Copy each block into the path shown in its header.

---

# 📁 File tree (suggested)

```
.
├─ docs/
│  └─ CONTEXT.md
├─ agents/
│  ├─ deals_ingestor.md
│  ├─ vc_crawler.md
│  ├─ social_enricher.md
│  └─ intro_personalizer.md
├─ db/
│  └─ schema.sql
├─ prompts/
│  ├─ system.mdx
│  └─ intro_prompt.md
└─ .env.example
```

---

# docs/CONTEXT.md

```md
# Project Context: VC Network Intel (1‑week MVP)

## Goal
End‑to‑end pipeline to (1) fetch crypto VC deals, (2) crawl VC sites for team members, (3) enrich contacts with socials (Farcaster, X/Twitter; infer Telegram handle), and (4) generate a short personalized intro message for each target contact.

## Outcomes (by EOW)
- Postgres DB with orgs/people/deals/evidence/intros tables.
- 3 automated pipelines + intro generator.
- Retool/Airtable as ops UI for review/edits.

## High‑level architecture
- **Orchestrator:** LangGraph (Python) for explicit state, retries, and shared DB writes.
- **DB:** Postgres (source of truth). Optional: Neo4j later for path queries.
- **Queue/Cache:** Redis (rate limit buckets, retries, dedup).
- **Crawling:** Playwright (headless). Respect robots.txt & ToS.
- **APIs:** Crypto raises (e.g., DefiLlama fundraising); Farcaster via provider (e.g., Neynar); X/Twitter if token available. Telegram handle **inference only** for MVP.
- **UI:** Retool or Airtable views on top of Postgres (read/write for text fields).

## Data model (essentials)
- **orgs**(org_id, name, website, domains[], kind, sources, created_at, updated_at)
- **deals**(deal_id, org_id, round, amount_eur, announced_on, investors[], source, uniq_hash)
- **people**(person_id, canonical_name, emails[], socials, telegram_handle, sources, confidence, updated_at)
- **roles_employment**(person_id, org_id, title, start_date, end_date, source, confidence)
- **evidence**(evidence_id, person_id, org_id, url, selector, snapshot_url, kind, extracted, created_at)
- **intros**(intro_id, person_id, org_id, draft_md, rationale, created_at)
- **events/jobs** tables for audit & reliability (optional for MVP; recommended).

## Agents (ownership & responsibilities)
1) **Deals Ingestor** — fetch raises, normalize startups/investors, idempotent upserts.
2) **VC Crawler** — discover Team pages, extract (name, title, profile URL), store evidence.
3) **Social Enricher** — find Farcaster & X/Twitter; infer Telegram handle; set confidence.
4) **Intro Personalizer** — generate 2 variants of short outreach copy; store to `intros`.

## Concurrency & safety
- Idempotent DB writes (upserts by `uniq_hash`/natural keys + versioning if needed).
- Rate limits and polite crawling; exponential backoff with jitter.
- Provenance: always persist `source` (url, ts, extractor) in `evidence`.
- ToS guardrails: **no LinkedIn scraping in MVP**; Telegram: do not read messages.

## One‑week plan
- **D1**: repo + Docker; migrations; Retool/Airtable connected.
- **D2**: deals ingestor; first rows in `orgs/deals`.
- **D3**: crawler for team pages; evidence snapshots; people/roles populated.
- **D4**: social enrichment; Telegram inference.
- **D5**: intro generation; storage + review screen.
- **D6**: glue (retries, schedules); QA.
- **D7**: polish; CSV export; quick README.

## Prompts & tone
- Respectful, concise, 2–3 sentences; avoid scraping claims; state value + light CTA.
```

---

# agents/deals_ingestor.md

````md
# Agent: Deals Ingestor

**Input:** None (scheduled) or date window
**Output:** Upserted rows in `orgs` and `deals`

## Steps
1. Fetch recent crypto raises (API client).
2. Normalize currency → EUR; compute `uniq_hash = sha1(name|date|round|amount_eur)`.
3. Upsert `orgs` for startups and `orgs` for investors (kind = 'startup' | 'vc').
4. Insert `deals` with `uniq_hash` for idempotency.

## Pseudocode
```python
for r in fetch_raises(since):
    startup = upsert_org(name=r.company, website=r.website, kind='startup', sources=r.source)
    investors = [upsert_org(name=i, kind='vc') for i in r.investors]
    upsert_deal(org_id=startup.id, round=r.round, amount_eur=to_eur(r.amount, r.currency),
                announced_on=r.date, investors=[i.name for i in investors], source=r.source,
                uniq_hash=sha1(...))
````

## Notes

* Handle duplicates by website/domain; fallback to name match with domain heuristics.

````

---

# agents/vc_crawler.md
```md
# Agent: VC Crawler

**Input:** VC `orgs.website`
**Output:** `people`, `roles_employment`, `evidence`

## Strategy
- Discover team/about URLs by sitemap, nav anchors, regex (team|people|about|leadership).
- Use Playwright; wait for network idle; extract cards/links; capture page screenshot.

## Selectors (try in order)
- Semantic: elements with role=link and innerText matches /(team|people|partners)/i
- CSS fallbacks: `.team*, .people*, a[href*="team"], a[href*="people"], a[href*="leadership"]`
- Card patterns: `[class*="team" i] .card`, `img + h3`, `figure + h3`, microdata `itemprop=employee`.

## Output fields per person
- `name`, `title`, `profile_url`, `org_id`, `source.url`, `selector`, optional `headshot_url`.

## Evidence
- Store `url`, `selector`, `snapshot_url` (if using a screenshot store), extracted JSON chunk.
````

---

# agents/social_enricher.md

```md
# Agent: Social Enricher

**Input:** People lacking socials/telegram
**Output:** Updated `people.socials`, `telegram_handle`, `confidence`

## Farcaster
- Query by name + domain/email guess; prefer verified accounts; capture fid and username.

## X/Twitter (optional if API key present)
- Query by name + org; require recent activity OR company match in bio.

## Telegram (inference only)
- If a profile explicitly lists Telegram → use it.
- Else, if Farcaster or X handle is present and **exactly identical** (case‑insensitive) to a known Telegram handle pattern, set `telegram_handle` with `confidence` 0.6 (explicit listing → 0.9).

## Confidence scoring (suggestion)
- 0.9 explicit link; 0.75 name+company match + recent activity; 0.6 handle parity only.
```

---

# agents/intro_personalizer.md

```md
# Agent: Intro Personalizer

**Input:** person_id, org_id
**Output:** `intros.draft_md` (2 variants) + `rationale`

## Prompt recipe
- System prompt from `prompts/system.mdx`.
- Few‑shot examples (optional) using realistic VC outreach.
- Context fields: person name, title, org focus, latest deal from `deals`, any shared ties (Farcaster follow, mutual startup), and your value prop.

## Style
- 2–3 sentences, specific, respectful, no scraping mentions, soft CTA.

## Example structure
1) Hook: specific to their fund focus or recent deal.
2) Why you: 1‑line value prop.
3) Soft CTA: "Open to a quick intro? Happy to send a 3‑bullet overview."
```

---

# db/schema.sql

```sql
-- Organizations & deals
create table if not exists orgs (
  org_id uuid primary key default gen_random_uuid(),
  name text not null,
  website text,
  domains text[] default '{}',
  kind text check (kind in ('vc','startup','other')) default 'other',
  sources jsonb default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists deals (
  deal_id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs(org_id),
  round text,
  amount_eur numeric,
  announced_on date,
  investors text[] default '{}',
  source jsonb default '{}',
  uniq_hash text unique
);

-- People & roles
create table if not exists people (
  person_id uuid primary key default gen_random_uuid(),
  canonical_name text not null,
  emails text[] default '{}',
  socials jsonb default '{}',
  telegram_handle text,
  sources jsonb default '{}',
  confidence real default 0.0,
  updated_at timestamptz default now()
);

create table if not exists roles_employment (
  person_id uuid not null references people(person_id),
  org_id uuid not null references orgs(org_id),
  title text,
  start_date date,
  end_date date,
  source jsonb default '{}',
  confidence real default 0.5,
  primary key (person_id, org_id, title)
);

-- Evidence & intros
create table if not exists evidence (
  evidence_id uuid primary key default gen_random_uuid(),
  person_id uuid,
  org_id uuid,
  url text,
  selector text,
  snapshot_url text,
  kind text,
  extracted jsonb,
  created_at timestamptz default now()
);

create table if not exists intros (
  intro_id uuid primary key default gen_random_uuid(),
  person_id uuid,
  org_id uuid,
  draft_md text,
  rationale jsonb,
  created_at timestamptz default now()
);

-- Convenience indexes
create index if not exists idx_orgs_name on orgs using gin (to_tsvector('simple', name));
create index if not exists idx_people_name on people using gin (to_tsvector('simple', canonical_name));
create index if not exists idx_deals_date on deals(announced_on);
```

---

# prompts/system.mdx

```mdx
You are an assistant that drafts concise, respectful outreach messages to venture partners in the crypto/Web3 space.

**Always**
- Keep it to 2–3 sentences.
- Be specific: mention the person’s role, fund focus, or a recent deal if available.
- Avoid claiming or implying you scraped private sources.
- Offer a soft, reversible CTA ("open to a quick intro?" / "happy to share a 3‑bullet brief").
- No hype; clear value in plain English.

**Never**
- Invent personal facts, emails, or Telegram handles.
- Mention internal tooling or data collection methods.
```

---

# prompts/intro_prompt.md

```md
**Inputs**
- person: {name, title}
- org: {name, focus, latest_deal?}
- ties: {shared_follow?, mutual_startup?, farcaster_handle?, telegram_handle?}
- value_prop: short string you provide

**Template**
Hi {name} — noticed your work as {title} at {org}. {if latest_deal}Congrats on {latest_deal.round} with {latest_deal.org}{/if}; aligns with {org.focus}.

I’m {your_name} building {value_prop}. Given our {tie_snippet_if_any}, thought a quick intro could be useful. Open to a short chat? Happy to send a 3‑bullet overview.
```

---

# .env.example

```bash
# Postgres
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/agent_mvp

# Redis
REDIS_URL=redis://localhost:6379/0

# API keys (add only those you actually use)
FARCASTER_API_KEY=
TWITTER_BEARER_TOKEN=
DEFILLAMA_BASE_URL=https://api.llama.fi

# Crawling
PLAYWRIGHT_HEADLESS=true
CRAWL_CONCURRENCY=2
CRAWL_DELAY_MS=1500

# App
LOG_LEVEL=info
```
