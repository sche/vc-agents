# Triggering Agents from Retool - Quick Guide

## ✅ Yes, you can trigger agent runs from Retool!

I've created a FastAPI server that exposes your agents as REST API endpoints.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install fastapi uvicorn
```

### 2. Start API Server
```bash
make run-api
# Opens at http://localhost:8000
# API Docs at http://localhost:8000/docs
```

### 3. Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agents/find-websites` | POST | Find VC websites |
| `/agents/crawl` | POST | Crawl VC team pages |
| `/agents/enrich` | POST | Enrich social handles |
| `/vcs` | GET | List VCs |
| `/agent-runs` | GET | List agent run history |

## 📊 Retool Integration

### In Retool:
1. **Add REST API Resource**: Point to your API URL
2. **Create Queries**: One for each endpoint
3. **Add UI Components**: Buttons, tables, dropdowns
4. **Wire them up**: Button clicks → Run query → Show results

See full guide: [`docs/RETOOL_API.md`](../docs/RETOOL_API.md)

## 🌐 Deployment Options

### For Database + API:

**Recommended: Supabase (Database) + Railway (API)**
- Database: Supabase ($0 free tier, easy Retool integration)
- API: Railway ($5/month, auto-deploy from GitHub)

**Alternative: All-in-one**
- Railway: Both DB + API in one service
- Render: Both DB + API in one service

### Quick Deploy to Railway:

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Deploy
railway up

# Get URL
railway open
```

## 🔐 Security (Production)

Add API key authentication:
```python
# In Retool resource, add header:
X-API-Key: your-secret-key
```

## 📝 Example Retool Dashboard

```
┌─────────────────────────────────────────┐
│  VC Agents Control Panel                │
├─────────────────────────────────────────┤
│  Select VC: [Fabric Ventures ▼]        │
│  Limit: [10]                            │
│                                         │
│  [🔍 Find Websites] [👥 Crawl Team]    │
│  [📱 Enrich Socials]                   │
├─────────────────────────────────────────┤
│  Recent Agent Runs                      │
│  ┌─────────────────────────────────┐   │
│  │ Agent    Status    Stats        │   │
│  │ enricher ✓ Done   35/50 found  │   │
│  │ crawler  ✓ Done   16 people    │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

## 📚 Files Created

- **`src/api/main.py`** - FastAPI server with all endpoints
- **`docs/RETOOL_API.md`** - Complete integration guide
- **`Makefile`** - Added `make run-api` command

## 🎯 Next Steps

1. Test locally: `make run-api` → Open http://localhost:8000/docs
2. Deploy database to Supabase (see my previous message)
3. Deploy API to Railway
4. Configure Retool to use your API
5. Build your dashboard!
