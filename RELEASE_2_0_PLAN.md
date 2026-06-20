# Release 2.0 - Prosumer Apps Expansion
## Implementation plan for next session

Read this entire file before doing anything. This is a self-contained brief.

---

## What this release does

Expands the RAG system from **EV charging apps only** to **two categories**:
- `ev_charging` - ChargePoint, EVgo, Blink, PlugShare, Electrify America, FLO, EVCS, Shell Recharge, Tesla
- `prosumer` - Tesla Powerwall, Enphase Enlighten, SolarEdge mySolarEdge, Emporia Energy, Sense, SunPower, Generac PWRview, Span

The backend architecture is **unchanged**. This is mostly a configuration + data + UI change.

---

## Current system state (as of v1.1.0)

- **Branch:** work on `dev`, release from `release/v2.0.0` → `main` → tag `v2.0.0`
- **Postgres:** `document_chunks` table, 11,322 chunks, pgvector, blr1 DO cluster
- **Embedding:** BAAI/bge-small-en-v1.5, 384 dims - DO NOT CHANGE
- **LLM:** claude-sonnet-4-6
- **UI:** Streamlit at https://168.144.26.72
- **Key files:**
  - `rag/retriever.py` - SYSTEM_PROMPT, ALL_APPS, retrieve functions
  - `rag/chat_ui/app.py` - sidebar filters (app, source, comparison mode)
  - `pipeline/run_pipeline.py` - SOURCE_READERS dict, all ingestion logic
  - `pipeline/scrapers/` - google_play.py, app_store.py, news_rss.py, web_pages.py, youtube.py
  - `rag/chat_ui/pipeline_db.py` - SOURCES list
  - `rag/chat_ui/pages/1_Admin_Portal.py` - APPS list, SOURCE_META
  - `config/.env` - all credentials (live, do not regenerate)
  - `config/users.yaml` - user accounts with bcrypt passwords

---

## Step-by-step implementation

### STEP 1 - Git branch

```bash
git checkout dev
git checkout -b feature/prosumer-expansion
git push origin feature/prosumer-expansion
```

---

### STEP 2 - DB schema migration (ONE change only)

Run this against the live DB (use `DATABASE_ADMIN_URL` from `config/.env`):

```python
# Run once - idempotent
import os, psycopg2
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path("config/.env"), override=True)
conn = psycopg2.connect(os.environ["DATABASE_ADMIN_URL"])
with conn:
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE document_chunks
              ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'ev_charging';

            CREATE INDEX IF NOT EXISTS idx_dc_category
              ON document_chunks(category);

            -- All 11,322 existing chunks are already ev_charging (default)
            -- Verify:
            SELECT category, COUNT(*) FROM document_chunks GROUP BY category;
        """)
conn.close()
```

Also update `pipeline/ingestion/upsert.py` to accept and write the `category` field:

In `upsert.py`, the INSERT statement needs `category` added to the column list.
Current INSERT is likely:
```sql
INSERT INTO document_chunks (source, app_name, content, metadata, embedding)
```
Change to:
```sql
INSERT INTO document_chunks (source, app_name, category, content, metadata, embedding)
```
And pass `chunk.get("category", "ev_charging")` as the value.

---

### STEP 3 - Update `pipeline/run_pipeline.py`

**3a. Add prosumer app readers**

Each existing reader (read_google_play, read_app_store, read_news, read_web_pages, read_youtube)
needs to also accept a `category` parameter and pass it through to each doc dict.

Change each doc append from:
```python
docs.append({
    "source":   "google_play",
    "app_name": app_dir.name,
    "content":  content,
    "metadata": {...},
})
```
To:
```python
docs.append({
    "source":    "google_play",
    "app_name":  app_dir.name,
    "category":  category,        # NEW - passed in from main()
    "content":   content,
    "metadata":  {...},
})
```

**3b. Category routing in main()**

Add a `--category` CLI arg and a category config map:

```python
APP_CATEGORIES = {
    # EV Charging
    "chargepoint":        "ev_charging",
    "evgo":               "ev_charging",
    "blink":              "ev_charging",
    "plugshare":          "ev_charging",
    "electrify_america":  "ev_charging",
    "flo":                "ev_charging",
    "evcs":               "ev_charging",
    "shell_recharge":     "ev_charging",
    "tesla":              "ev_charging",
    # Prosumer
    "tesla_powerwall":    "prosumer",
    "enphase":            "prosumer",
    "solaredge":          "prosumer",
    "emporia":            "prosumer",
    "sense":              "prosumer",
    "sunpower":           "prosumer",
    "generac":            "prosumer",
    "span":               "prosumer",
}
```

When reading, look up category: `category = APP_CATEGORIES.get(app_dir.name, "ev_charging")`

---

### STEP 4 - Scrape prosumer app data

**Find the app store IDs first** (use `infrastructure/scripts/find_app_ids.py` and `find_ios_ids.py`).

Known app IDs (verify before running):

| App | Google Play ID | App Store ID |
|---|---|---|
| Enphase Enlighten | `com.enphase.mobile.enlighten` | `647040648` |
| SolarEdge mySolarEdge | `com.solaredge.homeowner` | `972914059` |
| Emporia Energy | `com.emporiaenergy.consumer` | `1454558218` |
| Sense | `com.sense.app` | `1024124455` |
| SunPower | `com.sunpower.sunpower` | `1103985988` |
| Generac PWRview | `com.generac.pwrview` | `1540163890` |
| Span | `com.span.homeapp` | `1560859003` |
| Tesla (Powerwall) | `com.teslamotors.tesla` | `444912505` (same Tesla app) |

**Create data directories** for each new app in:
- `data/raw/text/google_play/<app_name>/`
- `data/raw/text/app_store/<app_name>/`
- `data/raw/text/news/<app_name>/`
- `data/raw/text/web_pages/<app_name>/`

**Run scrapers** (do NOT re-run existing EV apps - data already in DB):
```bash
# For each new prosumer app:
python pipeline/scrapers/google_play.py --app enphase
python pipeline/scrapers/app_store.py   --app enphase
python pipeline/scrapers/news_rss.py    --app enphase
python pipeline/scrapers/web_pages.py   --app enphase
# Repeat for: solaredge, emporia, sense, sunpower, generac, span, tesla_powerwall
```

**Ingest** new prosumer data:
```bash
python pipeline/run_pipeline.py --source google_play --app enphase
python pipeline/run_pipeline.py --source app_store   --app enphase
# etc.
```

---

### STEP 5 - Update `rag/retriever.py`

**5a. Update SYSTEM_PROMPT** - make it domain-agnostic:

```python
SYSTEM_PROMPT = """\
You are a competitive intelligence analyst for a smart energy app research team.
Your knowledge base covers two categories of North American apps:

EV CHARGING APPS (category: ev_charging):
  ChargePoint, EVgo, Blink, PlugShare, Electrify America, FLO, EVCS, Shell Recharge, Tesla

PROSUMER / HOME ENERGY APPS (category: prosumer):
  Tesla Powerwall, Enphase Enlighten, SolarEdge mySolarEdge, Emporia Energy,
  Sense, SunPower, Generac PWRview, Span

Content sources per app:
  - google_play / app_store : user reviews
  - news                    : press coverage and articles
  - web_pages               : official website content
  - youtube                 : video summaries and tutorials

Answer questions using ONLY the provided context chunks.
Each chunk is tagged with source type, app name, and category.
Distinguish between user sentiment (reviews), company claims (web), and demonstrations (video).
Be specific, cite apps by name, highlight cross-app and cross-category comparisons when relevant.
If the context is insufficient, say so rather than guessing."""
```

**5b. Expand ALL_APPS list:**

```python
ALL_EV_APPS = [
    "chargepoint", "evgo", "blink", "plugshare",
    "electrify_america", "flo", "evcs", "shell_recharge", "tesla",
]

ALL_PROSUMER_APPS = [
    "tesla_powerwall", "enphase", "solaredge", "emporia",
    "sense", "sunpower", "generac", "span",
]

ALL_APPS = ALL_EV_APPS + ALL_PROSUMER_APPS
```

**5c. Add category filter to retrieve functions:**

Update `retrieve()` signature:
```python
def retrieve(question: str, app_filter=None, top_k=TOP_K,
             category_filter=None, min_youtube=2) -> list[dict]:
```

Add `WHERE category = %s` clause when `category_filter` is set.

Same pattern for `retrieve_per_app()` - accept `app_list` parameter so it can
operate on just EV apps, just prosumer apps, or all apps.

---

### STEP 6 - Update `rag/chat_ui/app.py` (UI - Option A)

**Option A design: Category selector → App selector**

Replace the current sidebar app selectbox with a two-level filter:

```python
# In sidebar Search Settings expander:
category_choice = st.selectbox(
    "Category",
    ["All categories", "EV Charging", "Prosumer"],
    key="category_choice"
)
category_filter = {
    "EV Charging": "ev_charging",
    "Prosumer":    "prosumer",
}.get(category_choice)   # None means all

# App list changes based on category
if category_filter == "ev_charging":
    app_options = ["All apps"] + ALL_EV_APPS
elif category_filter == "prosumer":
    app_options = ["All apps"] + ALL_PROSUMER_APPS
else:
    app_options = ["All apps"] + ALL_EV_APPS + ALL_PROSUMER_APPS

app_choice = st.selectbox("App", app_options, key="app_choice")
app_filter = None if app_choice == "All apps" else app_choice
```

Pass `category_filter` to `retrieve()`, `retrieve_by_source()`, `retrieve_per_app()`.

**Update page title and branding:**
- Old: "EV Charging App Research"
- New: "Smart Energy App Research" (or "EV & Prosumer App Research")

**Update APPS constant and EXAMPLE_QUESTIONS** to include prosumer examples:
```python
EXAMPLE_QUESTIONS = [
    "What are the most common complaints about ChargePoint?",
    "How does Enphase compare to SolarEdge on battery management UX?",
    "What features does Tesla Powerwall app offer vs third-party apps?",
    "Which prosumer apps have the best solar monitoring experience?",
]
```

---

### STEP 7 - Update `rag/chat_ui/pipeline_db.py`

No change to table schema needed. Just update the `SOURCES` list if needed (it's already correct).

Update `get_chunks_by_app_source()` display - the pivot table will naturally
pick up new app names.

---

### STEP 8 - Update `rag/chat_ui/pages/1_Admin_Portal.py`

Update the `APPS` list constant at the top:
```python
APPS = [
    # EV Charging
    "chargepoint", "evgo", "blink", "plugshare", "electrify_america",
    "flo", "evcs", "shell_recharge", "tesla",
    # Prosumer
    "tesla_powerwall", "enphase", "solaredge", "emporia",
    "sense", "sunpower", "generac", "span",
    "general",
]
```

Add a category grouping to the YouTube upload app selector (use `st.selectbox` with
grouped options or just a flat list).

---

### STEP 9 - Update `CLAUDE.md`

Update:
- "Target apps" section → add prosumer apps
- "Current state" chunk count → update after ingestion
- "Architecture" → note dual-category support

---

### STEP 10 - Git release flow

```bash
# When all changes are done and tested locally:
git add -A
git commit -m "feat: Release 2.0 - prosumer app expansion (EV + home energy)"

# Push feature branch
git push origin feature/prosumer-expansion

# Merge to dev
git checkout dev
git merge --no-ff feature/prosumer-expansion

# Cut release branch
git checkout -b release/v2.0.0 dev
git push origin release/v2.0.0

# Merge to main + tag
git checkout main
git merge --no-ff release/v2.0.0 -m "release: v2.0.0 - prosumer expansion"
git tag -a v2.0.0 -m "Release 2.0 - EV + Prosumer smart energy app research platform"
git push origin main --tags

# Sync dev
git checkout dev
git merge --no-ff main -m "chore: sync dev with v2.0.0 release"
git push origin dev

# Deploy to server
ssh -i "C:\Users\Admin\.ssh\ev_research_do" root@168.144.26.72 \
  "cd /opt/ev-research && git pull origin main && systemctl restart ev-research"
```

---

## Files changed summary

| File | Type of change |
|---|---|
| `pipeline/ingestion/upsert.py` | Add `category` column to INSERT |
| `pipeline/run_pipeline.py` | Add `APP_CATEGORIES` map, pass `category` to all readers |
| `rag/retriever.py` | Update SYSTEM_PROMPT, ALL_APPS, add `category_filter` param |
| `rag/chat_ui/app.py` | Add category selector to sidebar, update branding, update example questions |
| `rag/chat_ui/pages/1_Admin_Portal.py` | Update APPS list |
| `CLAUDE.md` | Update target apps, chunk count, architecture notes |
| DB (one-time) | `ALTER TABLE document_chunks ADD COLUMN category TEXT DEFAULT 'ev_charging'` |

**Files that do NOT need to change:**
- `rag/chat_ui/pipeline_db.py` - no logic change needed
- `rag/chat_ui/obs_db.py` - fully domain-agnostic already
- `rag/chat_ui/pages/2_Observability.py` - fully domain-agnostic already
- `rag/chat_ui/session_db.py` - no change
- `rag/api/query.py` - update only if exposing category filter via API
- All scrapers in `pipeline/scrapers/` - no change, work for any app
- `.github/workflows/` - no change
- `config/.env` - no change (same DB, same API keys)
- `config/users.yaml` - no change

---

## Estimated new chunk counts (after ingestion)

| Source | Existing (EV) | Est. New (Prosumer) | Total |
|---|---|---|---|
| google_play | 5,973 | ~4,000 | ~9,973 |
| app_store | 3,687 | ~2,500 | ~6,187 |
| news | 1,443 | ~800 | ~2,243 |
| web_pages | 112 | ~100 | ~212 |
| youtube | 107 | ~50 | ~157 |
| **TOTAL** | **11,322** | **~7,450** | **~18,772** |

---

## Key gotchas for the next session

1. **Do NOT re-run scrapers for existing EV apps** - data is already in the DB.
   Only run scrapers for the 8 new prosumer apps.

2. **Do NOT re-run `setup_db.py` or `update_schema.py`** - they drop/recreate tables.
   Use only the `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migration in Step 2.

3. **Embedding model stays at BAAI/bge-small-en-v1.5, 384 dims** - changing it would
   require re-embedding all 11,322+ existing chunks. Don't touch it.

4. **`load_dotenv` must use `override=True`** - see CLAUDE.md gotcha #1.

5. **Clear `__pycache__` on import errors** after editing retriever.py:
   ```
   Remove-Item -Recurse -Force rag\__pycache__, rag\chat_ui\__pycache__
   ```

6. **Model name is `claude-sonnet-4-6`** - not claude-sonnet-4-20250514 (retired).

7. **Tesla appears in BOTH categories** - `tesla` (EV charging app) and
   `tesla_powerwall` (prosumer/home energy). Use distinct `app_name` values
   so they don't collide in the DB. The Tesla app covers both EV and Powerwall
   but we treat them as separate research subjects.

8. **App Store scraper IDs** - verify the iOS app IDs listed above before running.
   Use `infrastructure/scripts/find_ios_ids.py` to look them up if unsure.

9. **Firecrawl credits** - ~450 credits remaining as of v1.0. Each web page
   scrape costs ~1-5 credits. Budget accordingly for 8 new apps.

---

## Definition of Done for Release 2.0

- [ ] `category` column exists in `document_chunks` with correct values
- [ ] All 8 prosumer apps scraped and ingested (Google Play + App Store minimum)
- [ ] Category selector in sidebar works (filters app list + retrieval)
- [ ] Comparison mode works across both categories (All categories)
- [ ] SYSTEM_PROMPT updated to mention both domains
- [ ] Observability dashboard shows new apps in distribution chart
- [ ] Admin Portal shows new apps in source cards and YouTube uploader
- [ ] All existing EV app queries still work correctly (regression test)
- [ ] At least 2 cross-category comparison queries tested (e.g. Tesla EV vs Tesla Powerwall UX)
- [ ] Deployed to production server
- [ ] v2.0.0 tagged and pushed to GitHub
