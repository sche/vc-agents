-- VC Agents Database Schema
-- PostgreSQL 14+

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- ORGANIZATIONS (VCs and Startups)
-- ============================================================================
CREATE TABLE orgs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(500) NOT NULL,
    kind VARCHAR(20) NOT NULL CHECK (kind IN ('vc', 'startup', 'accelerator', 'other')),
    website VARCHAR(1000),
    description TEXT,
    focus JSONB, -- e.g., ["DeFi", "Infrastructure", "Gaming"]
    location JSONB, -- {city: "SF", country: "US", region: "North America"}
    
    -- Metadata
    sources JSONB NOT NULL DEFAULT '[]'::jsonb, -- [{type: "defillama", url: "...", date: "2025-01-01"}]
    socials JSONB DEFAULT '{}'::jsonb, -- {twitter: "@fund", linkedin: "...", farcaster: "fund"}
    
    -- Deduplication
    uniq_key VARCHAR(255) UNIQUE, -- sha256(lowercase(name) + normalize(website))
    
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes for common queries
    CONSTRAINT orgs_name_kind_key UNIQUE (name, kind)
);

CREATE INDEX idx_orgs_kind ON orgs(kind);
CREATE INDEX idx_orgs_website ON orgs(website);
CREATE INDEX idx_orgs_focus ON orgs USING GIN(focus);
CREATE INDEX idx_orgs_sources ON orgs USING GIN(sources);

-- ============================================================================
-- DEALS (Funding Rounds)
-- ============================================================================
CREATE TABLE deals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    
    -- Deal details
    round VARCHAR(100), -- "Seed", "Series A", "IDO", etc.
    amount_eur NUMERIC(15, 2), -- normalized to EUR
    amount_original NUMERIC(15, 2),
    currency_original VARCHAR(10), -- "USD", "ETH", etc.
    
    announced_on DATE,
    investors JSONB DEFAULT '[]'::jsonb, -- ["a16z", "Paradigm", ...]
    
    -- Source tracking
    source JSONB NOT NULL, -- {type: "defillama", url: "...", scraped_at: "..."}
    
    -- Idempotency
    uniq_hash VARCHAR(64) UNIQUE NOT NULL, -- sha256(org_name|date|round|amount_eur)
    
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_deals_org_id ON deals(org_id);
CREATE INDEX idx_deals_announced_on ON deals(announced_on DESC);
CREATE INDEX idx_deals_round ON deals(round);
CREATE INDEX idx_deals_investors ON deals USING GIN(investors);

-- ============================================================================
-- PEOPLE (VC Partners, Associates, etc.)
-- ============================================================================
CREATE TABLE people (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Identity
    full_name VARCHAR(500) NOT NULL,
    email VARCHAR(255),
    
    -- Socials
    socials JSONB DEFAULT '{}'::jsonb, -- {twitter: "@user", farcaster: {fid: 123, username: "user"}, linkedin: "..."}
    telegram_handle VARCHAR(100),
    telegram_confidence NUMERIC(3, 2), -- 0.60 to 0.99
    
    -- Provenance
    discovered_from JSONB, -- {org_id: "...", url: "...", method: "crawler"}
    enrichment_history JSONB DEFAULT '[]'::jsonb, -- [{enricher: "farcaster", date: "...", result: {...}}]
    
    -- Deduplication hint (not enforced - same person can work at multiple orgs)
    uniq_key VARCHAR(255), -- sha256(lowercase(full_name) + primary_email)
    
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_people_full_name ON people(full_name);
CREATE INDEX idx_people_email ON people(email);
CREATE INDEX idx_people_telegram_handle ON people(telegram_handle);
CREATE INDEX idx_people_socials ON people USING GIN(socials);
CREATE UNIQUE INDEX idx_people_uniq_key ON people(uniq_key) WHERE uniq_key IS NOT NULL;

-- ============================================================================
-- ROLES / EMPLOYMENT (Who works where)
-- ============================================================================
CREATE TABLE roles_employment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id UUID NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    
    -- Role details
    title VARCHAR(255), -- "Partner", "Principal", "Investment Associate"
    seniority VARCHAR(50), -- "partner", "principal", "associate", "analyst"
    start_date DATE,
    end_date DATE,
    is_current BOOLEAN DEFAULT true,
    
    -- Source
    evidence_id UUID, -- FK to evidence table (optional)
    
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT unique_person_org_role UNIQUE (person_id, org_id, title, is_current)
);

CREATE INDEX idx_roles_person_id ON roles_employment(person_id);
CREATE INDEX idx_roles_org_id ON roles_employment(org_id);
CREATE INDEX idx_roles_is_current ON roles_employment(is_current);
CREATE INDEX idx_roles_seniority ON roles_employment(seniority);

-- ============================================================================
-- EVIDENCE (Crawl snapshots, API responses, etc.)
-- ============================================================================
CREATE TABLE evidence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- What was captured
    evidence_type VARCHAR(50) NOT NULL, -- "crawler_snapshot", "api_response", "screenshot"
    url VARCHAR(2000),
    selector VARCHAR(500), -- CSS/XPath selector used
    
    -- Raw data
    raw_html TEXT,
    raw_json JSONB,
    screenshot_url VARCHAR(1000), -- S3/cloud storage URL
    
    -- Extraction metadata
    extracted_data JSONB, -- Structured data extracted from this evidence
    extraction_method VARCHAR(100), -- "playwright_selector", "llm_parse", "regex"
    
    -- Related entities (optional FKs)
    org_id UUID REFERENCES orgs(id) ON DELETE SET NULL,
    person_id UUID REFERENCES people(id) ON DELETE SET NULL,
    
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_evidence_org_id ON evidence(org_id);
CREATE INDEX idx_evidence_person_id ON evidence(person_id);
CREATE INDEX idx_evidence_type ON evidence(evidence_type);
CREATE INDEX idx_evidence_url ON evidence(url);

-- ============================================================================
-- INTROS (Generated outreach messages)
-- ============================================================================
CREATE TABLE intros (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id UUID NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    
    -- Message content
    message TEXT NOT NULL,
    subject VARCHAR(500),
    
    -- Context used for generation
    context_snapshot JSONB, -- {org: {...}, deals: [...], ties: {...}, value_prop: "..."}
    
    -- Delivery tracking
    status VARCHAR(50) DEFAULT 'draft', -- draft, approved, sent, replied, bounced
    sent_at TIMESTAMPTZ,
    sent_via VARCHAR(50), -- "telegram", "email", "twitter_dm"
    
    -- Quality/review
    reviewed_by VARCHAR(255), -- human reviewer
    review_notes TEXT,
    
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_intros_person_id ON intros(person_id);
CREATE INDEX idx_intros_status ON intros(status);
CREATE INDEX idx_intros_created_at ON intros(created_at DESC);

-- ============================================================================
-- AGENT RUNS (Execution tracking for observability)
-- ============================================================================
CREATE TABLE agent_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Execution details
    agent_name VARCHAR(100) NOT NULL, -- "deals_ingestor", "vc_crawler", etc.
    status VARCHAR(50) NOT NULL, -- "running", "success", "failed", "partial"
    
    -- Input/output
    input_params JSONB,
    output_summary JSONB, -- {orgs_created: 5, deals_upserted: 12, errors: [...]}
    
    -- Performance
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_seconds INTEGER GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (completed_at - started_at))::INTEGER
    ) STORED,
    
    -- Error tracking
    error_message TEXT,
    error_trace TEXT,
    
    -- LangGraph state snapshot (optional)
    langgraph_state JSONB
);

CREATE INDEX idx_agent_runs_agent_name ON agent_runs(agent_name);
CREATE INDEX idx_agent_runs_status ON agent_runs(status);
CREATE INDEX idx_agent_runs_started_at ON agent_runs(started_at DESC);

-- ============================================================================
-- RATE LIMITS (Simple rate limiting without Redis for MVP)
-- ============================================================================
CREATE TABLE rate_limits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Rate limit key
    service VARCHAR(100) NOT NULL, -- "farcaster_api", "twitter_api", "crawler:vc.com"
    identifier VARCHAR(255) NOT NULL, -- API key hash, domain, IP, etc.
    
    -- Limits
    window_start TIMESTAMPTZ NOT NULL,
    window_duration_seconds INTEGER NOT NULL DEFAULT 3600, -- 1 hour default
    request_count INTEGER NOT NULL DEFAULT 0,
    max_requests INTEGER NOT NULL,
    
    -- Audit
    last_request_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT unique_rate_limit UNIQUE (service, identifier, window_start)
);

CREATE INDEX idx_rate_limits_service ON rate_limits(service, identifier);
CREATE INDEX idx_rate_limits_window_start ON rate_limits(window_start);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to relevant tables
CREATE TRIGGER update_orgs_updated_at BEFORE UPDATE ON orgs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_deals_updated_at BEFORE UPDATE ON deals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_people_updated_at BEFORE UPDATE ON people
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_roles_employment_updated_at BEFORE UPDATE ON roles_employment
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_intros_updated_at BEFORE UPDATE ON intros
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- VIEWS (Convenience queries)
-- ============================================================================

-- Active VCs with recent activity
CREATE VIEW active_vcs AS
SELECT 
    o.*,
    COUNT(DISTINCT d.id) as deal_count,
    MAX(d.announced_on) as last_deal_date,
    COUNT(DISTINCT r.person_id) as team_size
FROM orgs o
LEFT JOIN deals d ON o.id = d.org_id AND d.announced_on > NOW() - INTERVAL '2 years'
LEFT JOIN roles_employment r ON o.id = r.org_id AND r.is_current = true
WHERE o.kind = 'vc'
GROUP BY o.id;

-- People with enrichment status
CREATE VIEW people_enrichment_status AS
SELECT 
    p.*,
    (p.socials->>'twitter' IS NOT NULL) as has_twitter,
    (p.socials->>'farcaster' IS NOT NULL) as has_farcaster,
    (p.telegram_handle IS NOT NULL) as has_telegram,
    (p.email IS NOT NULL) as has_email,
    COALESCE(
        (p.socials->>'twitter' IS NOT NULL)::int +
        (p.socials->>'farcaster' IS NOT NULL)::int +
        (p.telegram_handle IS NOT NULL)::int +
        (p.email IS NOT NULL)::int,
        0
    ) as enrichment_score
FROM people p;

-- ============================================================================
-- SEED DATA (Optional - for testing)
-- ============================================================================

-- Example VC org
-- INSERT INTO orgs (name, kind, website, focus) VALUES
-- ('Example Ventures', 'vc', 'https://example.vc', '["DeFi", "Infrastructure"]');

COMMENT ON TABLE orgs IS 'Organizations: VCs, startups, accelerators';
COMMENT ON TABLE deals IS 'Funding rounds with normalized amounts';
COMMENT ON TABLE people IS 'Individual contacts (VC partners, team members)';
COMMENT ON TABLE roles_employment IS 'Who works where (many-to-many with history)';
COMMENT ON TABLE evidence IS 'Audit trail of all scraped/fetched data';
COMMENT ON TABLE intros IS 'Generated outreach messages';
COMMENT ON TABLE agent_runs IS 'Execution logs for LangGraph agents';
COMMENT ON TABLE rate_limits IS 'Simple rate limiting (alternative to Redis for MVP)';
