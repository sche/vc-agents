# Supabase DATABASE_URL - Quick Setup Guide

## 🎯 TL;DR - Get Your DATABASE_URL in 3 Steps

### Step 1: Create Supabase Project
1. Go to [supabase.com](https://supabase.com) and sign in
2. Click **"New Project"**
3. Set a **Database Password** (save it!)
4. Click **"Create new project"** and wait ~2 minutes

### Step 2: Get Your Connection String
1. Click the **"Connect"** button (top right of dashboard)
2. Choose **"Connection Pooling"** tab
3. You'll see 3 options - pick the right one:

#### ✅ For Railway/API Deployment (RECOMMENDED)
**Mode: Transaction**
```
postgres://postgres.abcdefgh:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

#### ✅ For Local Development
**Mode: Session**
```
postgres://postgres.abcdefgh:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:5432/postgres
```

#### ✅ For Database Migrations
**Direct Connection**
```
postgresql://postgres:[YOUR-PASSWORD]@db.abcdefgh.supabase.co:5432/postgres
```

### Step 3: Update Your .env File
```bash
# Copy the connection string and replace [YOUR-PASSWORD]
DATABASE_URL=postgres://postgres.abcdefgh:[YOUR-ACTUAL-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

## 🔑 Finding Your Password

**Don't know your password?**

1. Go to **Settings** → **Database** in Supabase
2. Scroll to **"Reset Database Password"**
3. Click **"Generate a new password"**
4. **Copy it immediately** - you can't see it again!
5. Update your connection string with the new password

## 📋 Connection String Breakdown

Let's decode the connection string:
```
postgres://postgres.abcdefgh:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
         └─────┬────┘ └──────┬──────┘ └───────────────┬────────────────────┘ └┬┘ └──┬──┘
           Project ID      Password              Host (region + pooler)    Port  Database
```

- **Project ID**: Unique identifier for your project (e.g., `abcdefgh`)
- **Password**: The database password you set
- **Host**: Supabase pooler in your chosen region
- **Port**:
  - `6543` = Transaction mode (for APIs/Railway)
  - `5432` = Session mode (for development) or Direct (for migrations)
- **Database**: Always `postgres` (default database)

## 🚨 Common Issues & Fixes

### "Can't find connection string"
- Click the **"Connect"** button (top right corner)
- Make sure you're looking at **"Connection Pooling"** tab, NOT "Connection String" tab

### "Password authentication failed"
- Your password in the URL is wrong
- Reset it: Settings → Database → Reset Database Password
- Replace `[YOUR-PASSWORD]` in the connection string

### "Too many connections" error
- You're using Direct connection (port 5432 to `db.xxxxx.supabase.co`)
- Switch to pooler: use `pooler.supabase.com` host instead

### "Prepared statement not supported"
- You're using Transaction mode (port 6543) with prepared statements
- Either:
  - Switch to Session mode (port 5432 on pooler)
  - OR disable prepared statements in your code (see main guide)

## ✅ Verify It Works

Test your connection:

```bash
# Test with psql
psql "YOUR_CONNECTION_STRING_HERE" -c "SELECT version();"

# Test with Python
python -c "
from sqlalchemy import create_engine
engine = create_engine('YOUR_CONNECTION_STRING_HERE')
with engine.connect() as conn:
    result = conn.execute('SELECT version()')
    print(result.fetchone())
"
```

## 🎨 Visual Guide

```
Supabase Dashboard
    ↓
Click "Connect" (top right)
    ↓
Choose "Connection Pooling" tab
    ↓
See 3 modes:
    ├── Transaction (port 6543) → For Railway/APIs ✅
    ├── Session (port 5432)     → For local dev
    └── Direct (port 5432)      → For migrations
    ↓
Copy the connection string
    ↓
Replace [YOUR-PASSWORD] with actual password
    ↓
Paste in .env as DATABASE_URL
    ↓
Done! 🎉
```

## 📚 Which Mode Should I Use?

| You're Setting Up... | Use This Mode | Port | Why? |
|---------------------|---------------|------|------|
| **Railway deployment** | Transaction | 6543 | Handles many concurrent connections from API |
| **Local development** | Session | 5432 | Stable connection, works with all tools |
| **Running migrations** | Direct | 5432 | Full PostgreSQL features, admin access |
| **Vercel/Netlify Functions** | Transaction | 6543 | Optimized for serverless |
| **Docker container** | Session or Transaction | 5432 or 6543 | Depends on connection pattern |

## 🔗 Full Documentation

For detailed setup, troubleshooting, and advanced configuration:
- See [SUPABASE_SETUP.md](./SUPABASE_SETUP.md) for complete guide
- See [Railway Deployment](./RAILWAY_DEPLOYMENT.md) for Railway-specific setup

## 💡 Pro Tips

1. **Save your password immediately** when creating the project - you can't retrieve it later!
2. **Use Transaction mode (port 6543)** for Railway - it scales better
3. **Use Session mode (port 5432)** for local development - more compatible
4. **Never commit** your .env file with the real password
5. **Test the connection** before deploying to make sure it works

---

Still stuck? Check the [Supabase Connection Docs](https://supabase.com/docs/guides/database/connecting-to-postgres)
