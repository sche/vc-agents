# 🎉 Retool is Ready!

## Access Your UI

**Open in browser:** http://localhost:3000

### First Time Setup

1. **Create admin account**
   - Email: your-email@example.com
   - Password: (choose a strong password)
   - Organization name: "VC Agents"

2. **Connect to your database**
   - Click **Resources** (left sidebar)
   - Click **Create new** → **PostgreSQL**
   - Fill in:
     - Name: `vc_agents_db`
     - Host: `host.docker.internal`
     - Port: `5432`
     - Database: `vc_agents`
     - Username: `postgres`
     - Password: `postgres`
     - SSL: **Disabled**
   - Click **Test connection** → Should say "Success!"
   - Click **Save**

3. **Create your first app**
   - Click **Apps** → **Create new** → **From scratch**
   - Try the example queries from `docs/RETOOL_SETUP.md`

## Quick Commands

```bash
# Start Retool
make retool-start

# Stop Retool
make retool-stop

# View logs
make retool-logs

# Restart
make retool-restart
```

## What You Can Do Now

### 1. Browse Organizations
See all 201 organizations (startups + VCs) loaded from DefiLlama.

### 2. View Deals
Explore 195 crypto funding deals with amounts, rounds, and investors.

### 3. Review Data Quality
Check for missing data, duplicates, or enrichment opportunities.

### 4. Prepare for Agents
Once you build the VC crawler and social enricher agents, you'll use Retool to:
- Review enriched contact data
- Approve/reject generated intros
- Trigger agent runs manually
- Monitor pipeline progress

## Next Steps

1. ✅ Retool is running
2. 🔜 Extract VCs from investor lists (scripts/load_defillama_deals.py)
3. 🔜 Build VC crawler agent
4. 🔜 Build social enricher agent
5. 🔜 Build intro generator
6. 🔜 Create Retool apps for each workflow

## Need Help?

- Full setup guide: `docs/RETOOL_SETUP.md`
- Example queries: See RETOOL_SETUP.md "Useful Queries" section
- Retool docs: https://docs.retool.com/

**Pro tip**: Start with a simple "Organizations Browser" table view to get familiar with the interface!
