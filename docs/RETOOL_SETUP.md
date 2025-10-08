# Retool Self-Hosted Setup

## Quick Start

### 1. Start Retool

```bash
# From project root
docker-compose -f docker-compose.retool.yml up -d

# Check logs
docker logs -f retool

# Wait for: "Retool is listening on port 3000"
```

### 2. Access Retool

Open browser: **http://localhost:3000**

First time:
1. Create admin account (email + password)
2. Organization name: "VC Agents"

### 3. Connect to Your Database

In Retool UI:
1. Click **Resources** (left sidebar)
2. Click **Create new** → **PostgreSQL**
3. Configure:
   ```
   Name: vc_agents_db
   Host: host.docker.internal
   Port: 5432
   Database: vc_agents
   Username: postgres
   Password: postgres
   SSL: Disabled
   ```
4. Click **Test connection** → Should say "Success!"
5. Click **Save**

### 4. Create Your First App

**Option A: Intro Review Dashboard**

1. Click **Apps** → **Create new** → **From scratch**
2. Name: "Intro Review"
3. Add **Table** component
4. In table query:
   ```sql
   SELECT
     i.id,
     i.subject,
     i.message,
     i.status,
     p.full_name as person_name,
     o.name as org_name,
     i.created_at
   FROM intros i
   JOIN people p ON i.person_id = p.id
   LEFT JOIN roles_employment r ON p.id = r.person_id
   LEFT JOIN orgs o ON r.org_id = o.id
   WHERE i.status = 'draft'
   ORDER BY i.created_at DESC;
   ```
5. Add **Button**: "Approve"
   - On click → New query:
   ```sql
   UPDATE intros
   SET status = 'approved'
   WHERE id = {{ table1.selectedRow.id }}
   RETURNING *;
   ```
6. Preview your app!

**Option B: Organizations Browser**

1. Click **Apps** → **Create new** → **From scratch**
2. Name: "Organizations"
3. Add **Table** component
4. In table query:
   ```sql
   SELECT
     id,
     name,
     kind,
     website,
     focus,
     created_at,
     (SELECT COUNT(*) FROM deals WHERE org_id = orgs.id) as deal_count
   FROM orgs
   ORDER BY created_at DESC;
   ```
5. Make table editable (click table → Inspector → Enable "Allow editing")
6. Add update query to save changes

---

## Useful Queries for Your Pipeline

### See all VCs (currently empty until you extract them)
```sql
SELECT * FROM orgs WHERE kind = 'vc' ORDER BY name;
```

### See all startups with deals
```sql
SELECT
  o.name,
  o.website,
  COUNT(d.id) as deal_count,
  SUM(d.amount_usd) as total_raised_usd
FROM orgs o
JOIN deals d ON o.id = d.org_id
WHERE o.kind = 'startup'
GROUP BY o.id
ORDER BY total_raised_usd DESC NULLS LAST;
```

### See investor participation (VCs from deal.investors JSONB)
```sql
SELECT
  investor,
  COUNT(*) as deal_count,
  SUM(d.amount_usd) as total_invested_usd
FROM deals d,
LATERAL jsonb_array_elements_text(d.investors) AS investor
GROUP BY investor
ORDER BY deal_count DESC
LIMIT 20;
```

### People enrichment status
```sql
SELECT
  p.full_name,
  p.email,
  p.telegram_handle,
  p.telegram_confidence,
  o.name as org_name,
  r.title,
  jsonb_array_length(p.enrichment_history) as enrichment_attempts
FROM people p
JOIN roles_employment r ON p.id = r.person_id
JOIN orgs o ON r.org_id = o.id
ORDER BY p.created_at DESC;
```

### Pending intros
```sql
SELECT
  i.subject,
  i.message,
  i.status,
  p.full_name,
  p.email,
  p.telegram_handle,
  i.created_at
FROM intros i
JOIN people p ON i.person_id = p.id
WHERE i.status = 'draft'
ORDER BY i.created_at DESC;
```

---

## Common Tasks

### Stop Retool
```bash
docker-compose -f docker-compose.retool.yml down
```

### Restart Retool
```bash
docker-compose -f docker-compose.retool.yml restart
```

### View Logs
```bash
docker logs -f retool
```

### Update Retool
```bash
docker-compose -f docker-compose.retool.yml pull
docker-compose -f docker-compose.retool.yml up -d
```

### Backup Retool Data
```bash
# Retool stores its data in Docker volume
docker run --rm -v vc-agents_retool_data:/data -v $(pwd):/backup \
  ubuntu tar czf /backup/retool-backup.tar.gz /data
```

---

## Troubleshooting

### Can't connect to database
- Make sure your Postgres is running: `psql -U postgres -d vc_agents -c "SELECT 1;"`
- Check `host.docker.internal` works from container:
  ```bash
  docker exec -it retool ping host.docker.internal
  ```

### Retool won't start
- Check logs: `docker logs retool`
- Try removing container and starting fresh:
  ```bash
  docker-compose -f docker-compose.retool.yml down -v
  docker-compose -f docker-compose.retool.yml up -d
  ```

### Port 3000 already in use
- Change port in docker-compose.retool.yml:
  ```yaml
  ports:
    - "3001:3000"  # Use 3001 instead
  ```

---

## Next Steps

1. ✅ Connect to database
2. 📊 Create "Organizations" browser app
3. 👥 Create "People Manager" app
4. 📝 Create "Intro Review" workflow
5. 🔘 Add buttons to trigger your Python agents

**Pro tip**: Retool apps can call your Python scripts via HTTP! You can:
- Create a simple Flask API that wraps your agents
- Trigger agents from Retool buttons
- Show real-time progress

Example:
```python
# api.py - Simple Flask wrapper for agents
from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/api/enrich-person/<person_id>')
def enrich_person(person_id):
    # Call your social enricher agent
    # result = run_social_enricher(person_id)
    return jsonify({"status": "started", "person_id": person_id})

if __name__ == '__main__':
    app.run(port=5000)
```

Then in Retool button:
```javascript
// Call your API
await fetch('http://localhost:5000/api/enrich-person/' + table1.selectedRow.id);
```
