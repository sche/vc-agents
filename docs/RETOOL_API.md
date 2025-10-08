# Retool Integration Guide

This guide shows how to trigger VC Agents from Retool using the REST API.

## Setup

### 1. Install API Dependencies

```bash
pip install fastapi uvicorn
```

### 2. Start the API Server

```bash
make run-api
# OR
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at: `http://localhost:8000`

API Docs: `http://localhost:8000/docs`

## Deployment Options

### Option 1: Deploy API alongside database on Railway/Render
- Deploy FastAPI app to same service as your database
- Use internal connection for database
- Expose API endpoint to Retool

### Option 2: Run API locally with ngrok (for testing)
```bash
# Terminal 1: Start API
make run-api

# Terminal 2: Expose via ngrok
ngrok http 8000
```

Use the ngrok URL in Retool (e.g., `https://abc123.ngrok.io`)

### Option 3: Deploy to Vercel/Railway (recommended for production)
```bash
# Railway
railway up

# Or use Railway's GitHub integration for auto-deploy
```

## API Endpoints

### 1. Find VC Websites
**Endpoint:** `POST /agents/find-websites`

**Request Body:**
```json
{
  "vc_name": "Fabric Ventures",  // Optional: specific VC
  "limit": 10                     // Optional: limit number
}
```

**Response:**
```json
{
  "status": "completed",
  "stats": {
    "total_vcs": 10,
    "websites_found": 8,
    "websites_updated": 8
  }
}
```

### 2. Crawl VC Team Pages
**Endpoint:** `POST /agents/crawl`

**Request Body:**
```json
{
  "vc_name": "Genesis Capital",  // Optional: specific VC
  "use_fallback": true            // Use Perplexity fallback
}
```

**Response:**
```json
{
  "status": "completed",
  "result": {
    "org_name": "Genesis Capital",
    "people_found": 16,
    "people_created": 10,
    "people_updated": 6
  }
}
```

### 3. Enrich Social Handles
**Endpoint:** `POST /agents/enrich`

**Request Body:**
```json
{
  "limit": 50  // Optional: limit number of people
}
```

**Response:**
```json
{
  "status": "completed",
  "stats": {
    "total_people": 50,
    "enriched": 35,
    "farcaster_found": 25,
    "twitter_found": 30,
    "telegram_inferred": 28
  }
}
```

### 4. List VCs
**Endpoint:** `GET /vcs?limit=100`

**Response:**
```json
{
  "total": 13,
  "vcs": [
    {
      "id": "uuid",
      "name": "Fabric Ventures",
      "website": "https://fabricvc.com"
    }
  ]
}
```

### 5. List Agent Runs
**Endpoint:** `GET /agent-runs?limit=50`

**Response:**
```json
{
  "total": 50,
  "runs": [
    {
      "id": "uuid",
      "agent_name": "social_enricher",
      "status": "completed",
      "started_at": "2025-10-08T19:44:33",
      "completed_at": "2025-10-08T19:44:43",
      "output_summary": {
        "total_people": 3,
        "enriched": 3
      }
    }
  ]
}
```

## Retool Configuration

### Step 1: Add REST API Resource

1. Go to **Resources** → **Create New** → **REST API**
2. Name: `VC Agents API`
3. Base URL: `http://your-api-url.com` (or ngrok URL for testing)
4. Headers:
   ```
   Content-Type: application/json
   ```

### Step 2: Create Queries in Retool

#### Query: Find Websites
```javascript
// Resource: VC Agents API
// Method: POST
// URL: /agents/find-websites
// Body:
{
  "vc_name": {{ vcNameInput.value || null }},
  "limit": {{ limitInput.value || null }}
}
```

#### Query: Crawl Teams
```javascript
// Resource: VC Agents API
// Method: POST
// URL: /agents/crawl
// Body:
{
  "vc_name": {{ vcNameInput.value || null }},
  "use_fallback": {{ useFallbackCheckbox.value }}
}
```

#### Query: Enrich Socials
```javascript
// Resource: VC Agents API
// Method: POST
// URL: /agents/enrich
// Body:
{
  "limit": {{ limitInput.value || null }}
}
```

#### Query: List VCs
```javascript
// Resource: VC Agents API
// Method: GET
// URL: /vcs?limit={{ limitInput.value || 100 }}
```

#### Query: List Agent Runs
```javascript
// Resource: VC Agents API
// Method: GET
// URL: /agent-runs?limit={{ limitInput.value || 50 }}
```

### Step 3: Create UI Components

#### Example: Website Finder Button
1. Add **Button** component
2. Label: "Find Websites"
3. On Click: Run query `findWebsites`
4. Show **Notification** on success/error

#### Example: Agent Runs Table
1. Add **Table** component
2. Data: `{{ agentRunsQuery.data.runs }}`
3. Columns:
   - Agent Name: `{{ item.agent_name }}`
   - Status: `{{ item.status }}`
   - Started: `{{ item.started_at }}`
   - Duration: `{{ moment(item.completed_at).diff(moment(item.started_at), 'seconds') }}s`
   - Summary: `{{ JSON.stringify(item.output_summary) }}`

#### Example: VC Selector Dropdown
1. Add **Select** component
2. Data: `{{ listVcsQuery.data.vcs }}`
3. Label: `{{ item.name }}`
4. Value: `{{ item.name }}`

### Step 4: Create Dashboard Layout

```
┌─────────────────────────────────────────┐
│  VC Agents Control Panel                │
├─────────────────────────────────────────┤
│                                         │
│  [VC Dropdown ▼]  [Limit: 10]          │
│                                         │
│  [Find Websites]  [Crawl Teams]        │
│  [Enrich Socials]                      │
│                                         │
├─────────────────────────────────────────┤
│  Agent Runs History                     │
│  ┌─────────────────────────────────┐   │
│  │ Agent    │ Status │ Time │ Stats│   │
│  ├──────────┼────────┼──────┼──────┤   │
│  │ enricher │ ✓      │ 10s  │ {...}│   │
│  │ crawler  │ ✓      │ 45s  │ {...}│   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

## Advanced: Background Jobs

For long-running tasks, use background processing:

```python
# In main.py
@app.post("/agents/crawl")
async def run_crawler(request: CrawlerRequest, background_tasks: BackgroundTasks):
    # Start immediately
    background_tasks.add_task(run_crawler_task, request)
    return {"status": "started", "message": "Crawler started in background"}

def run_crawler_task(request: CrawlerRequest):
    # Long-running task
    crawler = VCCrawler()
    crawler.crawl_all_vcs()
```

Then poll `/agent-runs` to check status.

## Security (Production)

### Option 1: API Key Authentication
```python
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

@app.post("/agents/crawl")
async def run_crawler(
    request: CrawlerRequest,
    api_key: str = Depends(api_key_header)
):
    if api_key != os.getenv("API_KEY"):
        raise HTTPException(401, "Invalid API key")
    # ... rest of code
```

In Retool, add header:
```
X-API-Key: your-secret-key
```

### Option 2: OAuth (for team access)
Use FastAPI OAuth2 with Retool's OAuth integration.

## Troubleshooting

### CORS Errors (if Retool hosted)
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-org.retool.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Connection Timeout
Increase Retool query timeout to 60s for long-running agents.

### Database Connection Issues
Ensure API can access your database (same VPC or public with SSL).

## Next Steps

1. ✅ Deploy API to Railway/Render
2. ✅ Add API resource in Retool
3. ✅ Create queries for each agent
4. ✅ Build dashboard UI
5. ✅ Add authentication (production)
6. ✅ Set up monitoring/logging
