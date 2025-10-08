# VC Crawler Agent Documentation

## Overview

The VC Crawler Agent automatically discovers and extracts team member information from VC firm websites. It uses intelligent navigation to find team pages and leverages OpenAI GPT-4o-mini for structured data extraction.

## Features

### 🎯 Intelligent Team Page Discovery
- **Common Paths**: Tries `/team`, `/about`, `/people`, `/leadership`, etc.
- **LLM Analysis**: Uses GPT-4o-mini to analyze navigation menus when paths fail
- **Fallback Strategy**: Multi-level approach ensures high success rate

### 📊 Data Extraction
- **Structured Output**: name, title, profile_url, headshot_url
- **Full URLs**: Converts relative paths to absolute URLs with domain
- **Confidence Tracking**: All extractions scored at 0.9 (direct extraction)

### 🔄 Smart Refresh Logic
- **Time-Based**: Only updates people last crawled ≥30 days ago (configurable)
- **Configurable**: Set `RECRAWL_AFTER_DAYS` in `.env` (default: 30)
- **Force Override**: `--force-refresh` flag to update all regardless of age
- **Stats Tracking**: Separate counts for created/updated/skipped

### 📝 Evidence Trail
- **Screenshots**: Full-page captures stored in `data/screenshots/`
- **Extracted Data**: JSON stored in `evidence.extracted_data`
- **Extraction Method**: Tracks "openai_gpt4o_mini" as method
- **Source URL**: Original team page URL preserved

### 🔗 Database Integration
- **People Table**: Stores in `people.full_name`, `people.socials`
- **Roles Table**: Creates `roles_employment` linking person→org
- **Evidence Table**: Audit trail with type "vc_crawler_extraction"
- **Enrichment History**: Tracks all updates in `people.enrichment_history`

## Usage

### CLI Commands

```bash
# Crawl all VCs (respects 30-day refresh threshold)
python -m src.agents.vc_crawler

# Crawl specific VC by name
python -m src.agents.vc_crawler --vc-name "Paradigm"

# Limit number of VCs to crawl
python -m src.agents.vc_crawler --limit 5

# Force refresh all people (ignore age threshold)
python -m src.agents.vc_crawler --force-refresh

# Combine options
python -m src.agents.vc_crawler --vc-name "Sequoia" --force-refresh
```

### Makefile Targets

```bash
# Run VC crawler
make run-crawler
```

### Environment Configuration

```bash
# Required
OPENAI_API_KEY=sk-...

# Optional (defaults shown)
RECRAWL_AFTER_DAYS=30  # Update threshold in days
```

## Output Examples

### First Run (New VC)
```
🕷️  Starting VC Crawler Agent...
Loading base URL: https://www.paradigm.xyz
Found team page at: https://www.paradigm.xyz/team
Extracting people from: https://www.paradigm.xyz/team
Extracted 26 people from https://www.paradigm.xyz/team
✅ Paradigm: 26 created, 0 updated, 0 skipped, 26 roles
```

### Second Run (Next Day)
```
✅ Paradigm: 0 created, 0 updated, 26 skipped, 0 roles
   (All people within 30-day threshold)
```

### After 31+ Days
```
✅ Paradigm: 0 created, 26 updated, 0 skipped, 26 roles
   (Stale data refreshed automatically)
```

### Force Refresh
```
🔄 Force refresh mode enabled - will update all people regardless of age
✅ Paradigm: 0 created, 26 updated, 0 skipped, 26 roles
```

## Architecture

### Class: VCCrawler

**Methods:**
- `__init__()`: Initialize OpenAI client, create screenshot directory
- `get_website_from_sources(org)`: Extract website from org.website or org.sources
- `find_team_page(browser, base_url)`: Discover team page URL
- `extract_people_from_page(browser, team_url, org_id)`: Extract structured data
- `save_person(person_data, org_id, base_url)`: Save/update person (returns status)
- `save_role(person_id, org_id, title)`: Create employment role
- `save_evidence(person_id, person_data, base_url)`: Store audit trail
- `crawl_vc(org)`: Process single VC (returns stats)
- `crawl_all_vcs(limit)`: Process multiple VCs (returns overall stats)

### Data Flow

```
1. Get VC org from database
   ↓
2. Extract website from org.website or org.sources
   ↓
3. Find team page (common paths → LLM analysis)
   ↓
4. Extract people data (GPT-4o-mini + Playwright)
   ↓
5. For each person:
   - Check if exists (by full_name)
   - Check age (updated_at vs RECRAWL_AFTER_DAYS)
   - Skip if too recent, update if stale, create if new
   - Convert relative URLs to absolute
   - Save to people table with socials
   - Create role_employment record
   - Store evidence with screenshot
   ↓
6. Commit transaction
   ↓
7. Return stats (created/updated/skipped)
```

### Database Schema

**people table:**
```python
{
    "full_name": "Matt Huang",
    "socials": {
        "profile_url": "https://www.paradigm.xyz/team/matt-huang",
        "headshot_url": "https://www.paradigm.xyz/images/matt-huang.jpg"
    },
    "discovered_from": {
        "source": "vc_crawler",
        "org_id": "38e1be1d-d936-420a-bc33-c4cb1a4d4c9b",
        "url": "https://www.paradigm.xyz/team"
    },
    "enrichment_history": [
        {
            "timestamp": "2025-10-08T12:00:00",
            "source": "vc_crawler_refresh",
            "org_id": "38e1be1d-d936-420a-bc33-c4cb1a4d4c9b",
            "updated_fields": ["socials"]
        }
    ]
}
```

**evidence table:**
```python
{
    "evidence_type": "vc_crawler_extraction",
    "url": "https://www.paradigm.xyz/team",
    "screenshot_url": "data/screenshots/org_38e1be1d_1728394501.123.png",
    "extracted_data": {
        "name": "Matt Huang",
        "title": "Co-Founder & Managing Partner",
        "profile_url": "https://www.paradigm.xyz/team/matt-huang",
        "headshot_url": "https://www.paradigm.xyz/images/matt-huang.jpg",
        "confidence": 0.9
    },
    "extraction_method": "openai_gpt4o_mini",
    "person_id": "453a62f7-2799-4599-9b24-e8396f45a792"
}
```

## Performance

### Costs (per VC)
- **OpenAI API**: ~$0.02-0.05 per VC (GPT-4o-mini)
- **Screenshots**: ~1-5 MB per VC
- **Time**: 10-30 seconds per VC (network dependent)

### Rate Limits
- No built-in rate limiting (respects OpenAI limits)
- Sequential processing (not parallel)
- Configurable delay via `CRAWLER_REQUEST_DELAY_MS` (default: 1000ms)

### Efficiency
- **Smart Refresh**: Skips recently crawled people (saves API calls)
- **Idempotent**: Safe to re-run multiple times
- **Deduplication**: By full_name (considers updating same person logic)

## Error Handling

### Common Errors

**1. No Website Found**
```python
stats["error"] = "No website found"
# Check org.website and org.sources
```

**2. Team Page Not Found**
```python
stats["error"] = "Team page not found"
# LLM couldn't identify team link in navigation
```

**3. Extraction Failed**
```python
# JSON parsing error from LLM response
# Returns empty list [], no people created
```

**4. Database Errors**
```python
# Logs error, continues to next person
# Transaction rolls back, no partial saves
```

### Logging

```python
# Debug: Skipped people
logger.debug("Skipping Matt Huang - last updated 5 days ago (threshold: 30 days)")

# Info: Created/Updated
logger.info("Created person: Matt Huang")
logger.info("Updated person: Matt Huang (last update was 45 days ago)")

# Warning: No website
logger.warning("No website for Genesis Capital")

# Error: Extraction failed
logger.error("Error crawling Paradigm: type object 'Person' has no attribute 'name'")
```

## Future Improvements

- [ ] Parallel processing with async/await
- [ ] Better duplicate detection (fuzzy name matching)
- [ ] Extract email addresses from team pages
- [ ] Detect role seniority (Partner vs Analyst)
- [ ] Track org_id in deduplication (same name, different orgs)
- [ ] LangGraph integration for complex navigation
- [ ] Redis caching for team page URLs
- [ ] Retry logic with exponential backoff

## Testing

### Manual Testing

```bash
# Test single VC
python -m src.agents.vc_crawler --vc-name "Paradigm"

# Verify results
psql -U postgres -d vc_agents -h localhost -c \
  "SELECT p.full_name, r.title, o.name
   FROM people p
   JOIN roles_employment r ON p.id = r.person_id
   JOIN orgs o ON r.org_id = o.id
   WHERE o.name = 'Paradigm';"

# Check evidence
psql -U postgres -d vc_agents -h localhost -c \
  "SELECT evidence_type, url, extraction_method
   FROM evidence
   WHERE evidence_type = 'vc_crawler_extraction'
   LIMIT 5;"
```

### Test VCs

Pre-configured test VCs with known team pages:
- Andreessen Horowitz (a16z.com)
- Sequoia Capital (sequoiacap.com)
- Paradigm (paradigm.xyz)
- Multicoin Capital (multicoin.capital)
- Pantera Capital (panteracapital.com)

## Troubleshooting

### Issue: No people extracted
**Solution**: Check screenshot in `data/screenshots/` to see what was captured. Team page might use JavaScript rendering that Playwright didn't wait for.

### Issue: Relative URLs stored
**Solution**: Ensure `base_url` is passed to `save_person()` and `save_evidence()`. Check URL conversion logic.

### Issue: Duplicates created
**Solution**: Current deduplication is by `full_name` only. Consider adding org_id to uniqueness check.

### Issue: Skipping too many people
**Solution**: Lower `RECRAWL_AFTER_DAYS` or use `--force-refresh` flag.
