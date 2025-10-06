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


## High-level plan
- **1**: repo + Docker; migrations; Retool/Airtable connected.
- **2**: deals ingestor; first rows in `orgs/deals`.
- **3**: crawler for team pages; evidence snapshots; people/roles populated.
- **4**: social enrichment; Telegram inference.
- **5**: intro generation; storage + review screen.
- **6**: glue (retries, schedules); QA.
- **7**: polish; CSV export; quick README.


## Prompts & tone
- Respectful, concise, 2–3 sentences; avoid scraping claims; state value + light CTA.