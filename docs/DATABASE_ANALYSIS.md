# Database Structure Analysis

## Current Structure Assessment

### ✅ What Works Well

**1. Core Tables Are Solid**
- **orgs**: Clean separation by `kind` (vc/startup/accelerator/other)
- **deals**: Good normalization with FK to orgs
- **people**: Flexible with JSONB for socials and enrichment history
- **roles_employment**: Proper many-to-many with temporal tracking
- **evidence**: Complete audit trail
- **intros**: Ready for message generation

**2. Good Design Patterns**
- ✅ UUIDs for all primary keys (distributed-friendly)
- ✅ Timestamps on all tables (audit trail)
- ✅ JSONB for flexible semi-structured data
- ✅ Proper foreign key constraints with CASCADE
- ✅ Unique constraints for deduplication
- ✅ Check constraints for enum-like fields

**3. Deduplication Strategy**
- ✅ `uniq_key` (SHA256) for orgs - works well
- ✅ `uniq_hash` (SHA256) for deals - prevents duplicates
- ✅ Name-based matching for people - simple and effective

**4. Metadata & Provenance**
- ✅ `sources` JSONB array - tracks data lineage
- ✅ `enrichment_history` - tracks all updates
- ✅ `discovered_from` - origin tracking
- ✅ Evidence table - complete audit trail

## 🔧 Potential Improvements

### 1. People Deduplication (Minor Issue)

**Current:** Matches only by `full_name`
```python
stmt = select(Person).where(Person.full_name == person_data["name"])
```

**Problem:**
- Same name at different VCs = collision
- "John Smith" at Sequoia vs "John Smith" at a16z

**Solutions:**

**Option A: Add org_id to uniqueness (Simple)**
```python
# Check if person exists at THIS org
stmt = select(Person).where(
    Person.full_name == person_data["name"],
    Person.discovered_from['org_id'].astext == org_id
)
```

**Option B: Use uniq_key with fuzzy matching (Better)**
```python
# Add to Person model
uniq_key: Mapped[str | None] = mapped_column(String(255), unique=True)

# Generate: SHA256(normalized_name + email_or_profile_url)
uniq_key = generate_person_uniq_key(
    name="Matt Huang",
    identifier=profile_url or email or org_id
)
```

**Recommendation:** Start with Option A (org_id check) for MVP, consider Option B later.

### 2. Role Deduplication (Current Limitation)

**Current Constraint:**
```python
UniqueConstraint("person_id", "org_id", "title", "is_current")
```

**Problem:**
- Person changes title at same org → creates duplicate roles
- No way to mark old role as ended

**Solution: Track role transitions**
```python
# When saving role, check for existing current role
existing_role = db.query(RoleEmployment).filter(
    RoleEmployment.person_id == person_id,
    RoleEmployment.org_id == org_id,
    RoleEmployment.is_current == True
).first()

if existing_role and existing_role.title != new_title:
    # End the old role
    existing_role.is_current = False
    existing_role.end_date = date.today()

    # Create new role
    new_role = RoleEmployment(
        person_id=person_id,
        org_id=org_id,
        title=new_title,
        is_current=True,
        start_date=date.today()
    )
```

**Impact:** Low priority for MVP, but good for long-term accuracy.

### 3. Missing Indexes (Performance)

**Current:** Basic indexes on FKs and some fields

**Recommended additions:**
```sql
-- Frequently queried together
CREATE INDEX idx_people_fullname_discovered ON people (full_name, (discovered_from->>'org_id'));

-- Evidence lookups
CREATE INDEX idx_evidence_person_type ON evidence (person_id, evidence_type);
CREATE INDEX idx_evidence_org_type ON evidence (org_id, evidence_type);

-- Intro status queries
CREATE INDEX idx_intros_person_status ON intros (person_id, status);

-- Agent runs monitoring
CREATE INDEX idx_agent_runs_name_status ON agent_runs (agent_name, status);
```

**Impact:** Important when scaling to 1000s of people.

### 4. Data Integrity Constraints

**Missing but useful:**

```sql
-- Ensure confidence is 0-1
ALTER TABLE people
ADD CONSTRAINT people_telegram_confidence_range
CHECK (telegram_confidence >= 0 AND telegram_confidence <= 1);

-- Ensure end_date > start_date
ALTER TABLE roles_employment
ADD CONSTRAINT roles_employment_date_range
CHECK (end_date IS NULL OR end_date >= start_date);

-- Ensure status values
ALTER TABLE intros
ADD CONSTRAINT intros_status_check
CHECK (status IN ('draft', 'reviewed', 'sent', 'bounced', 'replied'));
```

**Impact:** Low priority, but prevents bad data.

## 📊 Current vs Ideal Schema

### People Table - Enhancement

**Current:**
```python
class Person(Base):
    full_name: Mapped[str]
    email: Mapped[str | None]
    socials: Mapped[dict[str, Any]]  # profile_url, headshot_url, twitter, etc.
    telegram_handle: Mapped[str | None]
    telegram_confidence: Mapped[float | None]
    discovered_from: Mapped[dict[str, Any] | None]
    enrichment_history: Mapped[list[dict]]
    uniq_key: Mapped[str | None]  # Currently unused
```

**Suggested improvements:**
```python
class Person(Base):
    # ... existing fields ...

    # Better deduplication
    uniq_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # SHA256(normalized_name + primary_identifier)

    # Add email domain for org matching
    email_domain: Mapped[str | None] = mapped_column(String(255), index=True)
    # Extracted from email, helps link person to org

    # Track last enrichment attempt
    last_enriched_at: Mapped[datetime | None]
    # Separate from updated_at (which tracks any field change)

    # Validation status
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # Mark if email bounced or verified
```

## 🎯 Recommendations for Current Sprint

### Priority 1: Fix People Deduplication
**Action:** Add org_id to person lookup in vc_crawler.py
```python
# Current (collision-prone)
stmt = select(Person).where(Person.full_name == person_data["name"])

# Better (org-aware)
discovered_from_filter = Person.discovered_from['org_id'].astext == org_id
stmt = select(Person).where(
    Person.full_name == person_data["name"],
    discovered_from_filter
)
```

**Effort:** 5 minutes
**Impact:** Prevents major bug with same names

### Priority 2: Add Performance Indexes
**Action:** Create migration script
```bash
# Create: migrations/001_add_performance_indexes.sql
```

**Effort:** 15 minutes
**Impact:** Future-proofs for scale

### Priority 3: Document Schema
**Action:** Update SCHEMA_SUMMARY.md with:
- ER diagram
- Index list
- Constraint explanations
- Query patterns

**Effort:** 30 minutes
**Impact:** Team alignment

## Conclusion

### ✅ Current Schema: **8/10**

**Strengths:**
- Well-normalized core structure
- Good use of JSONB for flexibility
- Proper foreign keys and constraints
- Complete audit trail via evidence table
- Timestamp tracking on all tables

**Weaknesses:**
- People deduplication needs org_id awareness
- Missing some performance indexes
- No role transition tracking
- uniq_key field exists but not used

### 🎯 For MVP: **Current structure is fine!**

The identified issues are:
- **People deduplication**: Quick fix, should do now (5 min)
- **Indexes**: Can wait until you have 1000+ people
- **Role transitions**: Nice to have, not critical
- **Constraints**: Edge case protection, low priority

### 🚀 Action Items

**Do Now (Before Social Enricher):**
1. ✅ Fix people deduplication to check org_id
2. ✅ Document the fix in code comments

**Do Later (When scaling):**
3. ⏳ Add performance indexes
4. ⏳ Implement role transition tracking
5. ⏳ Add data validation constraints

**Overall verdict: Your database structure is solid. Make the one-line fix to people deduplication and keep building!**
