# Railway Deployment Guide

This guide walks you through deploying the VC Agents API to Railway.

## Prerequisites

- [x] GitHub account with access to this repository
- [x] Railway account (free tier available at [railway.app](https://railway.app))

## 🚀 Quick Deploy (5 minutes)

### Step 1: Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Click **"Start a New Project"**
3. Select **"Deploy from GitHub repo"**
4. Authorize Railway to access your GitHub repos
5. Select the `vc-agents` repository

### Step 2: Add PostgreSQL Database

1. In your Railway project, click **"+ New"**
2. Select **"Database"** → **"PostgreSQL"**
3. Railway will automatically:
   - Create a PostgreSQL instance
   - Set `DATABASE_URL` environment variable
   - Link it to your API service

### Step 3: Configure Environment Variables

Click on your API service → **"Variables"** → Add these:

```bash
# Required
OPENAI_API_KEY=sk-...
PERPLEXITY_API_KEY=pplx-...
NEYNAR_API_KEY=...

# Optional
TWITTER_BEARER_TOKEN=...
ANTHROPIC_API_KEY=...

# Auto-configured by Railway
DATABASE_URL=postgresql://...  # Already set by Railway
PORT=...  # Already set by Railway
```

### Step 4: Initialize Database Schema

Once deployed, run the database initialization:

**Option A: Using Railway CLI**
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Run database initialization
railway run python -m src.db.init_db
```

**Option B: Using Railway Dashboard**
1. Go to your service → **"Deployments"**
2. Click on latest deployment → **"View Logs"**
3. Check if deployment succeeded
4. Use **"Run Command"** feature:
   ```bash
   python -m src.db.init_db
   ```

### Step 5: Test Your API

Railway will give you a URL like: `https://vc-agents-production.up.railway.app`

Test it:
```bash
curl https://your-app.railway.app/
# Should return: {"status":"ok","service":"vc-agents-api"}
```

API Documentation: `https://your-app.railway.app/docs`

## 📊 Connect to Retool

In Retool:

1. Go to **Resources** → **Create New** → **REST API**
2. Name: `VC Agents API`
3. Base URL: `https://your-app.railway.app`
4. Headers:
   ```
   Content-Type: application/json
   ```
5. Test connection with GET request to `/vcs`

## 🔧 Configuration Files

Your repo now has:

- **`railway.toml`** - Railway deployment config
- **`Procfile`** - Start command
- **`.railwayignore`** - Files to exclude from deployment

## 🔄 Auto-Deploy on Push

Railway automatically redeploys when you push to your main branch:

```bash
git add .
git commit -m "Update API"
git push origin main
# Railway will automatically deploy!
```

## 📦 What Gets Deployed

Railway will:
1. Clone your repo
2. Detect Python project (via `requirements.txt`)
3. Install dependencies
4. Run `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`
5. Expose your API on a public URL

## 🔍 Monitoring

### View Logs
```bash
# Using CLI
railway logs

# Or in Railway Dashboard
# Service → Deployments → Click deployment → View Logs
```

### Check Status
```bash
railway status
```

### Metrics
- Railway Dashboard shows:
  - CPU usage
  - Memory usage
  - Network traffic
  - Build times

## 💰 Pricing

**Free Tier:**
- $5 free credit/month
- Good for testing and low traffic

**Pro Plan ($20/month):**
- $20 usage credits included
- Usage-based billing after that
- ~$5-10/month for a small API + database

**Estimate for this project:**
- API: ~$5/month (512MB RAM, low CPU)
- PostgreSQL: ~$5/month (shared instance)
- **Total: ~$10/month**

## 🛡️ Security Best Practices

### 1. Add API Key Authentication (Optional)

Update `src/api/main.py`:
```python
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

@app.post("/agents/crawl", dependencies=[Depends(verify_api_key)])
async def run_crawler(...):
    # Your code
```

Add to Railway variables:
```
API_KEY=your-secret-key-here
```

### 2. Enable CORS (for Retool Cloud)

Already configured in `main.py`, but verify:
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

### 3. Use Railway Secrets

For sensitive data, use Railway's secret variables (marked with 🔒 icon).

## 🔧 Troubleshooting

### Build Fails
Check Railway logs:
```bash
railway logs --deployment
```

Common issues:
- Missing dependencies in `requirements.txt`
- Python version mismatch
- Database connection issues

### Database Connection Issues
Verify `DATABASE_URL` is set:
```bash
railway variables
```

### Port Issues
Railway sets `$PORT` automatically. Make sure you're using it:
```python
# Good ✅
uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

# Bad ❌
uvicorn.run(app, host="0.0.0.0", port=8000)  # Hardcoded port
```

### Slow Builds
Add `.railwayignore` to exclude large files (already added).

## 📚 Additional Resources

- [Railway Docs](https://docs.railway.app)
- [Railway Python Guide](https://docs.railway.app/guides/python)
- [Railway PostgreSQL](https://docs.railway.app/databases/postgresql)

## 🎯 Next Steps

1. ✅ Deploy to Railway
2. ✅ Initialize database schema
3. ✅ Test API endpoints
4. ✅ Connect Retool
5. ✅ Load initial data (DefiLlama deals)
6. ✅ Run agents from Retool dashboard

## 🚨 Important Notes

### Database Migration
If you already have local data:

```bash
# Export local database
pg_dump -U vc_user -d vc_agents > backup.sql

# Import to Railway
railway run psql $DATABASE_URL < backup.sql
```

### Environment Variables Security
- Never commit `.env` file to git
- Use Railway's encrypted variables
- Rotate API keys regularly

### Cost Control
- Monitor usage in Railway dashboard
- Set up usage alerts
- Use free tier for development
- Upgrade to Pro only when needed
