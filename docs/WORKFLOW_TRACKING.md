# Workflow Tracking

## Overview

The VC agents workflow now includes automatic tracking via the `agent_runs` table. Every agent execution creates a run record that captures:

- **Status**: `running`, `completed`, or `failed`
- **Input parameters**: VC details, configuration
- **Output summary**: Results (people created, errors, etc.)
- **Error messages**: What went wrong for failed runs
- **Timestamps**: Start and completion times

## How It Works

### Automatic Tracking

When any agent runs (e.g., VC Crawler), it:

1. **Creates a run record** with status `running`
2. **Executes the workflow** (find team page, extract people, etc.)
3. **Updates the record** with:
   - Status: `completed` or `failed`
   - Output: Statistics and results
   - Error message: If something went wrong

### Database Schema

The `agent_runs` table stores:

```sql
- id: UUID (primary key)
- agent_name: 'vc_crawler', 'vc_website_finder', etc.
- status: 'running', 'completed', 'failed'
- input_params: JSONB (org_id, org_name, etc.)
- output_summary: JSONB (people_created, people_skipped, etc.)
- started_at: TIMESTAMP
- completed_at: TIMESTAMP
- error_message: TEXT (for failed runs)
- error_trace: TEXT (stack trace if needed)
```

## Checking Workflow Status

### View All VCs

```bash
python -m scripts.check_workflow_status
```

Shows a table with:
- ✅ Completed VCs with results
- ❌ Failed VCs with error messages
- ❌ VCs that haven't been processed yet

### Filter by Status

```bash
# Show only failed VCs that need manual intervention
python -m scripts.check_workflow_status --status failed

# Show only completed VCs
python -m scripts.check_workflow_status --status completed

# Show only running VCs
python -m scripts.check_workflow_status --status running
```

### Filter by Agent

```bash
python -m scripts.check_workflow_status --agent vc_crawler
```

### View Detailed History for a VC

```bash
python -m scripts.check_workflow_status --vc "SMAPE"
```

Shows complete workflow history for that VC across all agent runs.

## Understanding the Output

### Status Icons

- ✅ **COMPLETED**: Agent ran successfully
- ❌ **FAILED**: Agent encountered an error
- 🔄 **RUNNING**: Agent is currently executing
- ❌ **NOT STARTED**: No workflow runs for this VC yet

### Common Failure Reasons

1. **"Team page not found"**
   - Website is inaccessible (DNS error, connection reset)
   - Website exists but has no team page
   - **Action**: Manually verify the website URL, consider updating or finding alternative sources

2. **"No website found"**
   - VC has no website in the database
   - **Action**: Run VC Website Finder agent first

3. **Network errors** (ERR_NAME_NOT_RESOLVED, ERR_CONNECTION_RESET)
   - Website is down or blocked
   - **Action**: Verify URL, check if website moved, update database

### Manual Intervention Guide

When the status checker shows failed VCs:

```
⚠️  VCs Requiring Manual Intervention:
   • Auros Global: Team page not found
   • Alchemy: Team page not found
   • Public Works: Team page not found
```

**Next Steps:**

1. **Verify the website URL** is correct:
   ```bash
   # Check what's in the database
   python -m scripts.check_workflow_status --vc "Auros"

   # Try accessing it manually
   curl -I https://www.aurosglobal.com
   ```

2. **Update the website** if it changed:
   ```sql
   UPDATE orgs
   SET website = 'https://correct-url.com'
   WHERE name = 'Auros Global';
   ```

3. **Re-run the crawler** for that specific VC:
   ```bash
   python -m src.agents.vc_crawler --vc-name "Auros"
   ```

4. **If the website is permanently unavailable**, consider:
   - Finding alternative sources (LinkedIn, Crunchbase)
   - Marking the VC as inactive
   - Using manual data entry

## Querying the Database Directly

### Find all failed runs

```sql
SELECT
    ar.agent_name,
    ar.input_params->>'org_name' as vc_name,
    ar.error_message,
    ar.started_at
FROM agent_runs ar
WHERE ar.status = 'failed'
ORDER BY ar.started_at DESC;
```

### Find VCs never processed

```sql
SELECT o.name, o.website
FROM orgs o
WHERE o.kind = 'vc'
  AND NOT EXISTS (
    SELECT 1 FROM agent_runs ar
    WHERE ar.input_params->>'org_id' = o.id::text
  );
```

### Get latest run for each VC

```sql
WITH latest_runs AS (
    SELECT DISTINCT ON (input_params->>'org_id')
        input_params->>'org_name' as vc_name,
        status,
        error_message,
        completed_at
    FROM agent_runs
    WHERE agent_name = 'vc_crawler'
    ORDER BY input_params->>'org_id', started_at DESC
)
SELECT * FROM latest_runs
ORDER BY completed_at DESC;
```

## Example Workflow

1. **Load deals** (creates VCs):
   ```bash
   make load-deals-limit
   ```

2. **Find websites** for VCs:
   ```bash
   python -m src.agents.vc_website_finder
   ```

3. **Crawl team members**:
   ```bash
   python -m src.agents.vc_crawler
   ```

4. **Check what failed**:
   ```bash
   python -m scripts.check_workflow_status --status failed
   ```

5. **Fix failed VCs** manually and re-run:
   ```bash
   python -m src.agents.vc_crawler --vc-name "Fixed VC Name"
   ```

6. **Verify all completed**:
   ```bash
   python -m scripts.check_workflow_status --status completed
   ```

## Benefits

✅ **Visibility**: Know exactly which VCs have been processed and which haven't
✅ **Debugging**: See error messages for failed runs
✅ **Idempotency**: Smart refresh prevents re-processing recent data
✅ **Audit Trail**: Complete history of all agent executions
✅ **Manual Intervention**: Clear signals when human action is needed
✅ **Progress Tracking**: Monitor long-running batch jobs

## Next Steps

After successfully crawling VCs, the next agents in the pipeline are:

1. **Social Enricher**: Find Farcaster, Twitter, Telegram handles
2. **Intro Generator**: Create personalized outreach messages
3. **Delivery**: Send intros via Telegram/Twitter
