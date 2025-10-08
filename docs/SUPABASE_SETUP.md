# Supabase Setup Guide

Complete guide to setting up Supabase as your PostgreSQL database for the VC Agents project.

## Why Supabase?

- **Free Tier**: 500MB database, 2GB bandwidth/month, unlimited API requests
- **Managed PostgreSQL**: Auto-backups, point-in-time recovery
- **Connection Pooling**: Built-in pgBouncer for better performance with serverless apps
- **Direct SQL Access**: Full PostgreSQL access, no ORM lock-in
- **Dashboard**: Web UI for database management and monitoring

## Step-by-Step Setup

### 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com)
2. Sign up or log in with GitHub
3. Click **"New Project"**
4. Fill in:
   - **Name**: `vc-agents` (or your preferred name)
   - **Database Password**: Generate a strong password (save this!)
   - **Region**: Choose closest to your users (e.g., `us-east-1` for US East Coast)
   - **Pricing Plan**: Free tier is sufficient to start
5. Click **"Create new project"**
6. Wait 2-3 minutes for provisioning

### 2. Get Connection Strings

Once your project is ready, click the **"Connect"** button at the top of your Supabase dashboard.

You'll see multiple connection string options:

#### **Option 1: Transaction Mode (Recommended for Railway/API)**
**Best for:** API servers, serverless functions, Railway deployment

```
postgres://postgres.apbkobhfnmcqqzqeeqss:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

- Uses **Supavisor** connection pooler on **port 6543**
- Transaction mode (for short-lived connections)
- Supports thousands of concurrent connections
- **Note:** Does not support prepared statements

#### **Option 2: Session Mode (For persistent connections with IPv4)**
**Best for:** Long-running servers that need IPv4 support

```
postgres://postgres.apbkobhfnmcqqzqeeqss:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres
```

- Uses **Supavisor** connection pooler on **port 5432**
- Session mode (maintains connection state)
- Supports both IPv4 and IPv6

#### **Option 3: Direct Connection (For migrations/admin)**
**Best for:** Database migrations, schema changes, admin tasks

```
postgresql://postgres:[YOUR-PASSWORD]@db.apbkobhfnmcqqzqeeqss.supabase.co:5432/postgres
```

- Direct connection to PostgreSQL on **port 5432**
- **Requires IPv6** (unless you have IPv4 add-on)
- Best for one-off scripts and migrations

### 3. Configure Environment Variables

Update your `.env` file based on your use case:

**For Railway/Production API (Transaction Mode):**
```bash
# Use Transaction Mode pooler (port 6543)
DATABASE_URL=postgres://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

**For Local Development:**
```bash
# Use Session Mode pooler (port 5432) - supports IPv4
DATABASE_URL=postgres://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:5432/postgres
```

**For Database Migrations:**
```bash
# Use Direct connection (port 5432) - requires IPv6
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
```

**Important Notes:**
- Replace `[YOUR-PASSWORD]` with your actual database password
- Replace `xxxxx` with your project reference ID
- Replace `us-east-1` with your chosen region
- Transaction mode (port 6543) does NOT support prepared statements
- You can get all connection strings by clicking **"Connect"** in Supabase dashboard

### 4. Initialize Database Schema

From your local machine, initialize the database schema:

```bash
# Option 1: Using direct connection (recommended for first-time setup)
# Temporarily set DATABASE_URL to the direct connection string
python -m src.db.init_db

# Option 2: Using psql directly
psql "postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres" -f db/schema.sql
```

This will create all tables: `orgs`, `deals`, `people`, `roles_employment`, `evidence`, `intros`, `agent_runs`.

### 5. Verify Setup

Check that tables were created:

```bash
# Option 1: Using Supabase Dashboard
# Go to Table Editor in left sidebar - you should see all tables

# Option 2: Using psql
psql "postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres" \
  -c "\dt"

# Option 3: Using Python
python -c "
from src.db.connection import get_db
with get_db() as db:
    result = db.execute('SELECT tablename FROM pg_tables WHERE schemaname=\'public\';')
    print([row[0] for row in result])
"
```

You should see: `orgs`, `deals`, `people`, `roles_employment`, `evidence`, `intros`, `agent_runs`.

### 6. Load Test Data (Optional)

Load some test VCs to verify everything works:

```bash
python scripts/add_test_vcs.py
```

Check the data:
```bash
python -c "
from src.db.connection import get_db
with get_db() as db:
    result = db.execute('SELECT name FROM orgs LIMIT 5;')
    for row in result:
        print(row[0])
"
```

## Supabase Dashboard Features

### Table Editor
- Browse and edit data visually
- Filter, sort, search
- Export to CSV
- Path: **Table Editor** in left sidebar

### SQL Editor
- Run custom SQL queries
- Save queries as snippets
- Path: **SQL Editor** in left sidebar

Example queries:
```sql
-- Count VCs
SELECT COUNT(*) FROM orgs WHERE kind = 'vc';

-- List recent deals
SELECT o.name, d.round, d.amount_eur, d.announced_on
FROM deals d
JOIN orgs o ON d.org_id = o.org_id
ORDER BY d.announced_on DESC
LIMIT 10;

-- Check enrichment progress
SELECT
  COUNT(*) as total_people,
  COUNT(*) FILTER (WHERE socials->>'twitter' IS NOT NULL) as with_twitter,
  COUNT(*) FILTER (WHERE socials->>'farcaster' IS NOT NULL) as with_farcaster,
  COUNT(*) FILTER (WHERE telegram_handle IS NOT NULL) as with_telegram
FROM people;
```

### Database Settings
- View connection strings
- Configure connection pooling
- Enable/disable extensions
- Path: **Settings** → **Database**

### Logs & Monitoring
- Query performance
- Slow queries
- Connection stats
- Path: **Logs** in left sidebar

## Connection Pooling Explained

Supabase provides three connection methods via **Supavisor** (their connection pooler):

### 1. Transaction Mode (Port 6543) - Recommended for APIs
- **Connection pooler**: Supavisor in transaction mode
- **Best for**: API servers, serverless functions, Railway deployment
- **Supports**: Thousands of concurrent connections
- **Limitations**:
  - Does NOT support prepared statements
  - Transactions must complete quickly (stateless)
  - Must disable prepared statements in your ORM/library

### 2. Session Mode (Port 5432) - For persistent apps
- **Connection pooler**: Supavisor in session mode
- **Best for**: Long-running servers, applications needing IPv4
- **Supports**: Both IPv4 and IPv6, connection state preservation
- **Limitations**: Fewer concurrent connections than transaction mode

### 3. Direct Connection (Port 5432) - For admin tasks
- **Direct to**: PostgreSQL database (no pooler)
- **Best for**: Database migrations, schema changes, one-off scripts
- **Supports**: Full PostgreSQL features
- **Limitations**:
  - Requires IPv6 (unless you have IPv4 add-on)
  - Limited concurrent connections (~60)

### Quick Reference Table

| Use Case | Connection Method | Port | Connection String Pattern |
|----------|------------------|------|---------------------------|
| **Railway/API deployment** | Transaction Mode | 6543 | `postgres://postgres.xxxxx:[PWD]@aws-0-[region].pooler.supabase.com:6543/postgres` |
| **Local development** | Session Mode | 5432 | `postgres://postgres.xxxxx:[PWD]@aws-0-[region].pooler.supabase.com:5432/postgres` |
| **Database migrations** | Direct Connection | 5432 | `postgresql://postgres:[PWD]@db.xxxxx.supabase.co:5432/postgres` |
| **One-off scripts** | Direct Connection | 5432 | `postgresql://postgres:[PWD]@db.xxxxx.supabase.co:5432/postgres` |

### Important: Disable Prepared Statements for Transaction Mode

If using **Transaction Mode (port 6543)**, you must disable prepared statements in your database library:

**SQLAlchemy:**
```python
from sqlalchemy import create_engine

# Add connect_args to disable prepared statements
engine = create_engine(
    DATABASE_URL,
    connect_args={"prepare_threshold": None}  # Disable prepared statements
)
```

**Prisma:**
```prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
  // Add pgbouncer=true for transaction mode
  relationMode = "prisma"
}
```

## Connecting from Railway

When deploying to Railway:

1. Add environment variable in Railway dashboard:
```
DATABASE_URL=postgresql://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

2. Railway will automatically use this for your app

3. To run migrations on Railway:
```bash
# SSH into Railway container
railway run bash

# Run migration
python -m src.db.init_db
```

Or use the direct connection URL from your local machine:
```bash
DATABASE_URL="postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres" \
  python -m src.db.init_db
```

## Security Best Practices

### 1. Password Management
- Never commit database passwords to git
- Use strong, generated passwords
- Rotate passwords periodically in Supabase dashboard

### 2. Network Security
- Supabase has IP restrictions available (Settings → Database → Network Restrictions)
- Free tier: Available to enable if needed
- Pro tier: More granular IP allowlisting

### 3. SSL/TLS
- All Supabase connections use SSL by default
- Connection strings include `?sslmode=require` automatically

### 4. Environment Variables
```bash
# .env (never commit this file!)
DATABASE_URL=postgresql://...

# Railway dashboard
# Add DATABASE_URL as environment variable (encrypted at rest)
```

## Troubleshooting

### "Too many connections" error
**Problem**: Exceeded connection limit

**Solution**:
1. Use pooled connection (port 6543) instead of direct (port 5432)
2. Close database sessions properly:
```python
# Always use context manager
with get_db() as db:
    # your queries here
    pass
# Connection automatically closed
```

### "Connection timeout"
**Problem**: Can't connect to Supabase

**Solution**:
1. Check your internet connection
2. Verify the connection string is correct
3. Check Supabase project status (supabase.com dashboard)
4. Ensure no firewall blocking port 5432 or 6543

### "SSL connection required"
**Problem**: Missing SSL mode

**Solution**: Add to connection string:
```
?sslmode=require
```
(Already included in Supabase connection strings)

### Schema changes not applying
**Problem**: Ran migration but changes not visible

**Solution**:
1. Ensure using direct connection (port 5432) for migrations
2. Check migration actually succeeded (look for errors)
3. Clear any connection pools:
```bash
# In Supabase dashboard: Database → Connection Pooling → Restart
```

### "relation does not exist" error
**Problem**: Tables not created

**Solution**:
```bash
# Re-run initialization
python -m src.db.init_db

# Or use SQL directly
psql "postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres" \
  -f db/schema.sql
```

## Migrating from Local PostgreSQL

If you have data in your local PostgreSQL database:

### 1. Export Local Data
```bash
# Export schema and data
pg_dump -U vc_user -h localhost vc_agents > local_backup.sql

# Or export just data (if schema already exists in Supabase)
pg_dump -U vc_user -h localhost vc_agents --data-only > data_only.sql
```

### 2. Import to Supabase
```bash
# Import full backup
psql "postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres" \
  < local_backup.sql

# Or import just data
psql "postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres" \
  < data_only.sql
```

### 3. Verify Migration
```bash
# Check row counts match
psql "postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres" \
  -c "SELECT
    (SELECT COUNT(*) FROM orgs) as orgs,
    (SELECT COUNT(*) FROM people) as people,
    (SELECT COUNT(*) FROM deals) as deals;"
```

## Cost Estimates

### Free Tier (Current)
- **Database**: 500MB storage
- **Bandwidth**: 2GB/month
- **API Requests**: Unlimited
- **Cost**: $0/month

### Pro Tier (If needed)
- **Database**: 8GB storage (+ $0.125/GB beyond)
- **Bandwidth**: 50GB/month (+ $0.09/GB beyond)
- **Point-in-time recovery**: 7 days
- **Daily backups**: Retained for 7 days
- **Cost**: $25/month

**For typical VC agents usage**: Free tier should be sufficient for:
- ~50-100 VCs
- ~500-1,000 people
- ~1,000 deals
- All enrichment data

Only upgrade if you exceed 500MB storage or 2GB bandwidth/month.

## Next Steps

After Supabase is set up:

1. ✅ Database is ready
2. 🚀 [Deploy API to Railway](RAILWAY_DEPLOYMENT.md)
3. 🔌 [Connect Retool](RETOOL_API.md)
4. 📊 Run your first pipeline:
```bash
make load-deals
make find-websites
make run-crawler
make run-enricher
```

## Resources

- [Supabase Documentation](https://supabase.com/docs)
- [Connection Pooling Guide](https://supabase.com/docs/guides/database/connecting-to-postgres#connection-pool)
- [Supabase SQL Editor](https://supabase.com/docs/guides/database/sql-editor)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
