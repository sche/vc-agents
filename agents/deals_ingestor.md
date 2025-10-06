# Agent: Deals Ingestor


**Input:** None (scheduled) or date window
**Output:** Upserted rows in `orgs` and `deals`


## Steps
1. Fetch recent crypto raises (API client).
2. Normalize currency → EUR; compute `uniq_hash = sha1(name|date|round|amount_eur)`.
3. Upsert `orgs` for startups and `orgs` for investors (kind = 'startup' | 'vc').
4. Insert `deals` with `uniq_hash` for idempotency.


## Pseudocode
```python
for r in fetch_raises(since):
    startup = upsert_org(name=r.company, website=r.website, kind='startup', sources=r.source)
    investors = [upsert_org(name=i, kind='vc') for i in r.investors]
    upsert_deal(org_id=startup.id, round=r.round, amount_eur=to_eur(r.amount, r.currency),
    announced_on=r.date, investors=[i.name for i in investors], source=r.source,
    uniq_hash=sha1(...))
```