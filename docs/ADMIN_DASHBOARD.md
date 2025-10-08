# Admin Dashboard

Simple, beautiful admin UI for managing VC Agents data.

## 🎯 Features

### Dashboard
- **Statistics Overview**: Total VCs, people, social enrichment status
- **Quick Actions**: Trigger agents for all VCs/people
- **Agent Runs Today**: See activity at a glance

### Organizations (VCs)
- **View all VCs** with search and filtering
- **Find websites** for specific VC or all VCs
- **Crawl teams** for specific VC or all VCs
- **Delete organizations** (with confirmation)
- **Filters**:
  - Search by name
  - With/without website
  - Sort by name, created date, updated date

### People
- **View all people** with search and filtering
- **Enrich social profiles** for specific person or all people
- **Edit Telegram handles** manually
- **View social profiles** (Twitter, Farcaster, Telegram)
- **Filters**:
  - Search by name
  - Enrichment status (Twitter, Farcaster, Telegram)
  - Sort by name, update date, confidence

### Agent Runs
- **View execution history** of all agents
- **Filter by agent type** (website_finder, vc_crawler, social_enricher)
- **Filter by status** (completed, failed, running)
- **See input/output data** for each run
- **View error messages** for failed runs

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install streamlit
# or
make install-dev
```

### 2. Start Admin Dashboard
```bash
make run-admin
```

The dashboard will open at **http://localhost:8501**

## 📖 Usage Guide

### For Non-Technical Users

#### View VCs
1. Go to **Organizations** page
2. Use search box to find specific VCs
3. Filter by "With website" or "Without website"
4. Click on any VC name to expand details

#### Find VC Website
**For single VC:**
1. Go to **Organizations** page
2. Find the VC you want
3. Click **"🔍 Find Website"** button

**For all VCs:**
1. Go to **Dashboard** page
2. Click **"🔍 Find All VC Websites"** button

#### Crawl VC Team
**For single VC:**
1. Go to **Organizations** page
2. Find the VC (must have website)
3. Click **"🕷️ Crawl Team"** button

**For all VCs:**
1. Go to **Dashboard** page
2. Click **"🕷️ Crawl All VCs"** button

#### Enrich Social Profiles
**For single person:**
1. Go to **People** page
2. Find the person
3. Click **"💼 Enrich"** button

**For all people:**
1. Go to **Dashboard** page
2. Click **"💼 Enrich All People"** button

#### Edit Telegram Handle
1. Go to **People** page
2. Find the person
3. Expand their card
4. Type Telegram handle in the text box (e.g., `@username`)
5. Click **"Save Telegram"** button

#### View Agent Runs
1. Go to **Agent Runs** page
2. Filter by agent type or status
3. Click on any run to see details
4. Check for errors in failed runs

#### Check Agent Status
- Look for these emoji indicators:
  - ✅ = Completed successfully
  - ❌ = Failed (click to see error)
  - ⏳ = Currently running
  - 🐦 = Has Twitter
  - 🟣 = Has Farcaster
  - ✈️ = Has Telegram

## 🎨 Interface Preview

### Dashboard Page
```
🚀 VC Agents Dashboard
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────┬─────────────┬─────────────┬─────────────┐
│ Total VCs   │ Total People│ Enrichment  │ Agent Runs  │
│    50       │     250     │  150 profiles│    Today: 5 │
│ 45 websites │ 120 Twitter │ 75 Telegram  │             │
└─────────────┴─────────────┴─────────────┴─────────────┘

Quick Actions
┌────────────────────────┬────────────────────────┬────────────────────────┐
│ 🔍 Find All VC Websites│ 🕷️ Crawl All VCs       │ 💼 Enrich All People   │
└────────────────────────┴────────────────────────┴────────────────────────┘
```

### Organizations Page
```
🏢 Organizations (VCs)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Search: [____________]  Website: [All ▼]  Sort: [Name ▼]

▼ Andreessen Horowitz ✅
  Name: Andreessen Horowitz
  Website: https://a16z.com
  Team members: 25

  [🔍 Find Website] [🕷️ Crawl Team] [🗑️ Delete]

▼ Sequoia Capital ⚠️ No website
  Name: Sequoia Capital
  Website: Not found
  Team members: 0

  [🔍 Find Website] [🗑️ Delete]
```

### People Page
```
👥 People
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Search: [____________]  Status: [All ▼]  Sort: [Name ▼]

▼ Marc Andreessen 🐦 🟣 ✈️
  Name: Marc Andreessen
  Organization: Andreessen Horowitz
  Title: Co-founder & Managing Partner
  Twitter: @pmarca (confidence: 0.95)
  Farcaster: @pmarca (confidence: 0.90)
  Telegram: [@pmarca_____]  [Save Telegram]

  [💼 Enrich]

▼ Ben Horowitz 🐦
  Name: Ben Horowitz
  Organization: Andreessen Horowitz
  Title: Co-founder & Managing Partner
  Twitter: @bhorowitz (confidence: 0.93)
  Telegram: [___________]  [Save Telegram]

  [💼 Enrich]
```

### Agent Runs Page
```
🤖 Agent Runs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Agent: [All ▼]  Status: [All ▼]

▼ ✅ social_enricher - 2025-01-08 14:32:15
  Agent: social_enricher
  Status: completed
  Started: 2025-01-08 14:32:15
  Duration: 45.3s

  Input: {"person_id": "uuid-here"}
  Output: {"twitter_found": true, "farcaster_found": true}

▼ ❌ vc_crawler - 2025-01-08 14:15:03
  Agent: vc_crawler
  Status: failed
  Started: 2025-01-08 14:15:03
  Duration: 12.1s

  Error: Timeout while loading page
```

## 🔧 Configuration

### Port Configuration
Default: `http://localhost:8501`

To change:
```bash
streamlit run src/admin/app.py --server.port 9000
```

### Theme Customization
Create `.streamlit/config.toml`:
```toml
[theme]
primaryColor = "#FF4B4B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
```

## 🚨 Troubleshooting

### "No module named streamlit"
```bash
pip install streamlit
```

### "No organizations found"
Load some deals first:
```bash
make load-deals
```

### "No people found"
Run the VC crawler first:
```bash
make run-crawler
```

### Agent not responding
1. Check **Agent Runs** page for errors
2. Look for failed runs
3. Check error message in failed run details
4. Ensure API keys are set in `.env`

### Changes not showing
Click the **🔄 Refresh Data** button in the sidebar

## 💡 Tips

1. **Use filters** to narrow down large lists
2. **Sort by updated date** to see recently modified items
3. **Check Agent Runs** regularly to ensure everything is working
4. **Use search** to quickly find specific VCs or people
5. **Refresh data** after running agents to see new results

## 🔐 Security Note

This admin dashboard is meant for **internal use only**. Do not expose it to the public internet without proper authentication.

To add authentication, see: [Streamlit Authentication Guide](https://docs.streamlit.io/knowledge-base/deploy/authentication-without-sso)

## 📚 Next Steps

1. Start the admin: `make run-admin`
2. Load some deals: `make load-deals`
3. Find websites: Click "Find All VC Websites"
4. Crawl teams: Click "Crawl All VCs"
5. Enrich socials: Click "Enrich All People"
6. Monitor progress: Check "Agent Runs" page
