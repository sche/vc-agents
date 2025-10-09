# Admin Dashboard Railway Deployment

## Overview
The admin dashboard is a Streamlit app that provides a CRM-like interface for managing VCs, people, deals, and agent runs.

## Local Development
```bash
make run-admin
# Opens on http://localhost:8501
```

## Railway Deployment Options

### Option 1: Separate Railway Service (Recommended)

This approach keeps the API and admin as separate services, allowing independent scaling and clearer separation.

#### Steps:

1. **In Railway Dashboard:**
   - Go to your project
   - Click "+ New" → "Service" → "GitHub Repo"
   - Select your `vc-agents` repository
   - Name it `vc-agents-admin`

2. **Configure Service Settings:**
   - **Root Directory:** Leave as `/` (default)
   - **Build Command:** (auto-detected by nixpacks)
   - **Start Command:**
     ```bash
     streamlit run src/admin/app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
     ```

3. **Set Environment Variables:**
   Copy from your API service:
   - `DATABASE_URL` - Your Supabase connection string
   - `OPENAI_API_KEY` - Your OpenAI API key
   - `FIRECRAWL_API_KEY` - Your Firecrawl API key (if using)
   - Any other secrets from your API service

4. **Deploy:**
   - Railway will auto-deploy when you push to GitHub
   - Get your admin URL from Railway (e.g., `https://vc-agents-admin-production.up.railway.app`)

5. **Health Check (Optional):**
   - Streamlit doesn't have a built-in health endpoint
   - Railway will check if the process is running
   - You can add `healthcheckPath = "/"` but it may show as unhealthy (Streamlit redirects)

### Option 2: Using railway-admin.toml

Railway can detect multiple `.toml` files. To use the pre-configured admin config:

1. In Railway service settings, set:
   - **Railway Config File:** `railway-admin.toml`

2. The rest is handled by the config file automatically

### Option 3: Single Service Multi-Process (Not Recommended)

You could use the Procfile to run both, but Railway only exposes one port, so this won't work well:

```procfile
web: uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
admin: streamlit run src/admin/app.py --server.port 8501 --server.address 0.0.0.0
```

**Problem:** Only the `web` process gets the public URL. The admin would run but not be accessible.

## Security Considerations

⚠️ **IMPORTANT:** The admin dashboard has no authentication by default!

### Add Authentication

Option 1: Streamlit Cloud Authentication (if migrating to Streamlit Cloud)
- Streamlit Cloud provides built-in Google OAuth

Option 2: Basic HTTP Auth via Railway
- Use Railway's private networking
- Add a reverse proxy with basic auth

Option 3: Custom Streamlit Authentication
Add to `src/admin/app.py`:

```python
import streamlit as st
import os

def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == os.environ.get("ADMIN_PASSWORD", "changeme"):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input + error
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct
        return True

# Add this at the start of main()
if not check_password():
    st.stop()
```

Then set `ADMIN_PASSWORD` in Railway environment variables.

Option 4: VPN/Private Network (Most Secure)
- Use Railway's private networking
- Access via VPN or bastion host
- Keep admin internal-only

## Recommended Setup

For production, I recommend:

1. **Two Railway Services:**
   - `vc-agents-api` (already deployed) - Public API
   - `vc-agents-admin` (new) - Admin dashboard

2. **Add Basic Auth to Admin:**
   - Use the Streamlit password example above
   - Set `ADMIN_PASSWORD` env var in Railway

3. **Access Control:**
   - Share Railway URL + password only with your partner
   - Railway URLs are not guessable (long random strings)
   - Consider IP allowlisting if Railway supports it

## Post-Deployment

After deploying, you'll have:
- **API:** `https://vc-agents-api-production.up.railway.app`
- **Admin:** `https://vc-agents-admin-production.up.railway.app`

Both will share the same Supabase database via `DATABASE_URL`.

## Troubleshooting

### Playwright Browser Crashes on Railway

**Error:** `Page.screenshot: Target crashed` or `ERROR:gpu/command_buffer/service/shared_image/shared_image_manager.cc`

**Solution:** This is caused by GPU/shared memory issues in containerized environments. The fix has been applied to the code:

1. Browser launch flags include `--disable-gpu`, `--disable-dev-shm-usage`, `--no-sandbox`
2. Screenshot failures are handled gracefully (crawler continues without screenshots)
3. Set these environment variables in Railway:
   - `PYTHONUNBUFFERED=1` (for better logging)
   - Optional: `PLAYWRIGHT_BROWSERS_PATH=/tmp/playwright` (if needed)

If you still see crashes:
- Check Railway memory limits (upgrade to higher tier if needed)
- Screenshots may be disabled but crawler will still extract people data
- Perplexity fallback doesn't require browser/screenshots

### Admin won't start
- Check Railway logs for errors
- Ensure `DATABASE_URL` is set correctly
- Verify `streamlit` is in `requirements.txt`

### Can't access admin URL
- Streamlit redirects `/` to `/?` on first load (this is normal)
- Check Railway deployment logs for the actual port binding
- Ensure `--server.port $PORT` is in start command

### Database connection errors
- Copy exact `DATABASE_URL` from API service
- Ensure `?sslmode=require` or `?sslmode=disable` matches your API config

### Sessions lost on refresh
- This is normal for Streamlit
- Railway free tier may sleep after inactivity
- Upgrade to Railway hobby plan for always-on services

## Cost Estimate

Railway Pricing (as of 2024):
- **Free Tier:** $5 of usage per month
- **Hobby Plan:** $5/month + usage
- **Two services** (API + Admin) will use ~2x resources

Typical usage:
- Small admin dashboard: ~$0.50-2/month
- API with moderate traffic: ~$2-5/month
- **Total:** ~$3-7/month on hobby plan

Alternatives:
- **Streamlit Community Cloud:** Free hosting for Streamlit apps (no API support)
- **Render:** Similar pricing to Railway
- **Fly.io:** Free tier available, pay-as-you-go

## Next Steps

1. ✅ Fix deal amount formatting (completed)
2. Deploy admin to Railway (follow Option 1 above)
3. Add authentication (use Streamlit password check)
4. Share admin URL with partner
5. Monitor Railway usage and costs
