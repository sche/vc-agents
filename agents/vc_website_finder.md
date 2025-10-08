# VC Website Finder Agent

**Status**: ✅ Production Ready (Enhanced with validation & tracking)
**Location**: `src/agents/vc_website_finder.py`
**Purpose**: Discover and validate official websites for VC organizations using LLM with automatic fallback patterns

## Overview

The VC Website Finder is an intelligent agent that finds official websites for venture capital firms. It uses GPT-4o-mini to identify the most likely official website URL for a VC firm based on its name.

## Strategy

The agent uses a conservative, high-precision approach:

1. **Check existing** → If `--force` flag used, validate existing URL first
2. **Extract from sources** → Look for domains in article sources (DefiLlama articles often link to VCs)
3. **LLM discovery** → Ask GPT-4o for the official website URL
4. **Validate** → Verify URL is reachable via HTTP request (automatic)
5. **No guessing** → If LLM fails or validation fails, return None (manual research needed)
6. **Update database** → Save validated website to `orgs.website` and add to `sources` array
7. **Track workflow** → Record run in `agent_runs` table for visibility

**Note**: The agent does NOT use domain pattern guessing (e.g., firmname.com, firmname.vc) as this creates too many false positives. For example, searching for "Alchemy" VC firm could incorrectly find alchemy.com (a blockchain infrastructure company). Manual research is better than wrong data.

## Usage

### Find websites for all VCs without websites

```bash
make find-websites
# or
python -m src.agents.vc_website_finder
```

**Note**: URL validation is **ALWAYS ENABLED**. The agent will:
- Validate LLM suggestions before accepting them
- Try domain pattern fallbacks if LLM URL fails
- Only update database with verified, reachable URLs

### Find website for specific VC

```bash
python -m src.agents.vc_website_finder --vc-name "Sequoia"
```

### Re-validate and fix websites even if already set

```bash
python -m src.agents.vc_website_finder --force
```

**What `--force` does:**
- Validates existing URLs via HTTP request
- If URL fails validation, clears it and tries to find a new one
- Uses LLM + domain pattern fallback to find valid alternatives
- Perfect for fixing broken/incorrect URLs

### Enable URL validation (optional)

**Note**: Validation is now **always enabled** by default. The `--validate` flag has been removed.

### Process limited number
```bash
python -m src.agents.vc_website_finder --limit 10
```

## CLI Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `--limit` | int | Maximum number of VCs to process |
| `--vc-name` | str | Process specific VC by name (fuzzy match) |
| `--force` | flag | Re-find websites even if already set |
| `--validate` | flag | Enable HTTP validation (off by default) |

## Output

The agent provides detailed statistics:

```
📊 Website Discovery Summary:
   VCs processed: 5
   Websites found: 3
   Already had website: 1
   LLM failed: 2
   Validation failed: 0
```

## LLM Prompt Strategy

The agent uses a carefully crafted prompt that:
- Provides the VC name
- Includes context from sources (domains found in articles)
- Shows examples of known VC websites
- Requests only the URL (no explanation)
- Returns "UNKNOWN" if not confident

Example prompt:
```
You are helping to find the official website for a venture capital firm.

VC Firm Name: "Paradigm"

Task: Return the official, primary website URL for this VC firm.

Rules:
- Return ONLY the URL in the format: https://example.com
- Use https:// protocol
- Return the main domain (not subpages like /team or /about)
- Use your knowledge to find the most likely official website
- If you absolutely cannot find it, return "UNKNOWN"

Examples:
- Sequoia Capital → https://www.sequoiacap.com
- Andreessen Horowitz → https://a16z.com
- Paradigm → https://www.paradigm.xyz

Your answer (URL only):
```

## Database Updates

The agent updates two fields in the `orgs` table:

1. **`website`** (VARCHAR) - The official website URL
2. **`sources`** (JSONB) - Appends a new source entry:

```json
{
  "type": "vc_website_finder",
  "url": "https://www.example.com",
  "method": "llm_discovery",
  "validated": true
}
```

## Performance

- **Cost**: ~$0.001-0.002 per VC (GPT-4o-mini)
- **Speed**: ~1-2 seconds per VC
- **Accuracy**: ~80-90% (depends on VC prominence)

## Error Handling

The agent gracefully handles:

- **LLM failures** → Returns "UNKNOWN", skips update
- **Validation failures** → Optional with `--skip-validation`
- **Database errors** → Rollback transaction, continue to next VC
- **HTTP timeouts** → 10 second timeout, treats as validation failure

## Integration with Other Agents

This agent is designed to run **before** the VC Crawler:

```bash
# 1. Load deals (extracts VCs from investors[])
make load-deals-limit

# 2. Find VC websites
make find-websites

# 3. Crawl VC team pages
make run-crawler
```

## Known Limitations

1. **Obscure VCs** → LLM may return "UNKNOWN" for very small/unknown firms
2. **DNS issues** → Validation can fail due to temporary DNS problems (use `--skip-validation`)
3. **Name ambiguity** → Generic names like "Alchemy" might find wrong domain
4. **Recent VCs** → Very new VCs might not be in LLM's training data

## Success Metrics

From testing on 5 VCs extracted from DefiLlama deals:

- ✅ **3/5 websites found** (60% success rate)
- ✅ **100% accuracy** on found websites
- ❌ **2/5 failed** (SMAPE Capital, Frachtis - likely don't exist or very obscure)

## Future Improvements

1. **Fallback to search API** → Use Google Custom Search for "UNKNOWN" cases
2. **Domain extraction from sources** → Parse article HTML for VC website links
3. **Manual mapping** → Hardcoded database of known VCs
4. **Confidence scores** → Return probability along with URL
5. **Better validation** → Check for VC-specific content (e.g., "portfolio", "team")

## Example Output

```
🔍 Starting VC Website Finder Agent...
Found 3 VCs to process

[1/3] Processing: Sequoia Capital
LLM response for Sequoia Capital: 'https://www.sequoiacap.com'
✅ Updated Sequoia Capital → https://www.sequoiacap.com

[2/3] Processing: Paradigm
LLM response for Paradigm: 'https://www.paradigm.xyz'
✅ Updated Paradigm → https://www.paradigm.xyz

[3/3] Processing: Unknown VC Fund
LLM response for Unknown VC Fund: 'UNKNOWN'
⚠️  No website found for Unknown VC Fund

============================================================
📊 Website Discovery Summary:
   VCs processed: 3
   Websites found: 2
   Already had website: 0
   LLM failed: 1
   Validation failed: 0
============================================================
```

## Dependencies

- `langchain-openai` - GPT-4o-mini for website discovery
- `httpx` - HTTP client for URL validation
- `sqlalchemy` - Database operations
- `loguru` - Logging

## Testing

To test the agent on a single VC:

```bash
# Test on well-known VC
python -m src.agents.vc_website_finder --vc-name "Sequoia"

# Test on obscure VC
python -m src.agents.vc_website_finder --vc-name "XYZ Capital"

# Test with validation
python -m src.agents.vc_website_finder --vc-name "Paradigm"

# Test without validation
python -m src.agents.vc_website_finder --vc-name "Paradigm" --skip-validation
```
