# Smart Energy App Research - RAG System (v2.0)
## Project brief for Claude Code

Read this entire file before doing anything.

---

## What this project is

A RAG knowledge base for competitive research on **EV charging and prosumer/home energy apps in the North American market**. Dual-category system (ev_charging + prosumer). Collects data from multiple sources, embeds with a local model, stores vectors in pgvector on DigitalOcean Postgres, and exposes a Streamlit chat interface backed by Claude.

---

## Target apps

**EV Charging:** ChargePoint, EVgo, Blink, PlugShare, Electrify America, FLO, EVCS, Shell Recharge, Tesla

**Prosumer / Home Energy:** Tesla Powerwall, Enphase Enlighten, SolarEdge mySolarEdge, Emporia Energy, Sense, SunPower, Generac PWRview, Span

---

## Architecture (FINAL - do not re-propose)

| Layer | Choice |
|---|---|
| Cloud | DigitalOcean |
| Droplet | NONE - pipeline runs locally on Windows |
| Data lake | Local disk C:\EVMarketResearch\data\ |
| Vector DB | pgvector on DO Managed Postgres (blr1) - `category` column added v2.0 |
| Embedding | BAAI/bge-small-en-v1.5 (local, 384 dims, already downloaded) |
| LLM | claude-sonnet-4-6 via Anthropic API |
| Chat UI | Streamlit - dual-category filter (ev_charging / prosumer) |

---

## Current state: FULLY BUILT AND LIVE (local + cloud)

**The system is complete and deployed.** Run locally with:
```
streamlit run rag/chat_ui/app.py
```
Opens at http://localhost:8501

**Cloud (production):** http://168.144.26.72
- DigitalOcean Droplet: s-1vcpu-2gb, Ubuntu 22.04, blr1, IP 168.144.26.72
- nginx (port 80 → 8501) + systemd service (`ev-research.service`), both enabled and running
- SSH: `ssh -i "C:\Users\Admin\.ssh\ev_research_do" root@168.144.26.72`
- Restart app: `systemctl restart ev-research`
- View logs: `journalctl -u ev-research -n 50`

**Postgres: 17,642 chunks live** (blr1, ev-research-db cluster)

| category | source | chunks |
|---|---|---|
| ev_charging | google_play | 5,973 |
| ev_charging | app_store | 3,687 |
| ev_charging | news | 1,443 |
| ev_charging | web_pages | 112 |
| ev_charging | youtube | 66 |
| prosumer | google_play | 2,500 |
| prosumer | app_store | 2,885 |
| prosumer | news | 864 |
| prosumer | web_pages | 112 |
| **TOTAL** | | **17,642** |

---

## All credentials set in config/.env

- DATABASE_URL - live (pipeline user)
- DATABASE_ADMIN_URL - live (doadmin user)
- ANTHROPIC_API_KEY - set (claude-sonnet-4-6)
- YOUTUBE_API_KEY - set (YouTube Data API v3)
- FIRECRAWL_API_KEY - set (free tier, ~450 credits remaining)
- DO_TOKEN, DO_SPACES_* - set (Spaces unused)

---

## File structure

```
C:\EVMarketResearch\
├-- config/.env                        LIVE - all creds set
├-- pipeline/
│   ├-- scrapers/
│   │   ├-- google_play.py             DONE
│   │   ├-- app_store.py               DONE
│   │   ├-- news_rss.py                DONE
│   │   ├-- youtube.py                 DONE (yt-dlp based)
│   │   ├-- web_pages.py               DONE (Firecrawl)
│   │   └-- parse_transcripts.py       DONE (manual transcript parser)
│   ├-- processing/
│   │   ├-- chunker.py                 DONE (512 tok / 64 overlap)
│   │   └-- embedder.py                DONE (bge-small-en-v1.5, 384 dims)
│   └-- ingestion/
│       └-- upsert.py                  DONE
├-- rag/
│   ├-- retriever.py                   DONE - shared embed→search→Claude logic
│   ├-- api/query.py                   DONE - FastAPI POST /query
│   └-- chat_ui/app.py                 DONE - Streamlit UI
└-- data/raw/text/
    ├-- google_play/   7 app folders, reviews.json each
    ├-- app_store/     9 app folders, reviews.json each
    ├-- news/          9 app folders + _general, articles.json each
    ├-- youtube/       6 app folders, transcripts.json each (21 videos)
    └-- web_pages/     9 app folders, pages.json each (25 pages)
```

---

## Streamlit UI features

- Sidebar: **Category** selector (All / EV Charging / Prosumer) → **App** selector → **Source** filter, **Comparison mode** toggle, chunks-per-app slider
- **Comparison mode**: fetches N chunks (default 3) per app - respects category filter, scales to 9 or 17 apps
- Live KB chunk count queried from Postgres (cached 5 min)
- Chat history, expandable source citations with score
- Example question buttons on empty state

---

## Key technical gotchas (read before touching code)

1. **`load_dotenv` must use `override=True`** in `rag/retriever.py` - `ANTHROPIC_API_KEY` was already set (empty) in the Windows system environment. Without override, the empty value wins and all Claude calls fail with auth error.

2. **Clear `__pycache__` on import errors** - if Streamlit shows `ImportError` for a function that clearly exists in the file, stale bytecode is the cause:
   ```
   Remove-Item -Recurse -Force rag\__pycache__, rag\chat_ui\__pycache__, rag\api\__pycache__
   ```
   Then restart Streamlit.

3. **YouTube automated scraper is IP-rate-limited** - `youtube.py` uses yt-dlp but YouTube blocks transcript access from this IP. The scraper code is correct; 21 transcripts were added manually via `parse_transcripts.py`. Do NOT re-run `youtube.py` without waiting ~1 hr.

4. **Model name**: `claude-sonnet-4-6` (not `claude-sonnet-4-20250514` - that ID is retired).

5. **Do NOT re-run** any already-done scrapers or `setup_db.py` / `update_schema.py` - data is live.

6. **Do NOT change** embedding model or vector dimensions - 384-dim is baked into all existing chunks.

7. **sentence-transformers must load before psycopg2 on Windows** - a DLL conflict between PyTorch and psycopg2 causes a hard segfault if psycopg2 is imported first. Fixed by: (a) pinning `sentence-transformers==3.0.1` in requirements.txt, (b) making the import eager at the top of `embedder.py`, (c) reordering imports in `retriever.py` so embedder is imported before psycopg2.

---

## Pipeline runner

```
python pipeline/run_pipeline.py --source [google_play|app_store|news|youtube|web_pages]
```

All 5 sources are wired. youtube reads from `data/raw/text/youtube/*/transcripts.json`.

---

## Key technical specs

- Chunk size: 512 tokens, 64-token overlap (tiktoken cl100k_base)
- Embedding: BAAI/bge-small-en-v1.5, 384 dims, local CPU
- Top-K retrieval: 8 (normal mode) or N×9 (comparison mode)
- Python venv: `.venv\Scripts\python.exe`

---

## Admin Portal - DONE (rag/chat_ui/pages/1_Admin_Portal.py)

- 5 tabs: Overview · Data Sources · Automation · Run Logs · 👥 Users
- Role-based access: superadmin (full) / superuser (read-only) / user (blocked)
- Users tab: add user (email as username), delete, change role, reset/generate password, shareable credentials block
- Passwords stored as bcrypt hash in config/users.yaml
- Background scheduler thread: fires overdue weekly pipeline jobs every 30 min
- YouTube upload: upload .txt summary file → triggers pipeline_bg("youtube")

## 🚀 NEXT: Release 2.0 - Prosumer App Expansion

**Full implementation plan in `RELEASE_2_0_PLAN.md` - read that file first.**

Summary: Expand from EV-only to dual-category (ev_charging + prosumer).
New apps: Tesla Powerwall, Enphase, SolarEdge, Emporia, Sense, SunPower, Generac PWRview, Span.
Backend is unchanged - one DB column, updated SYSTEM_PROMPT, category filter in UI (Option A).

Branch: `feature/prosumer-expansion` off `dev` → `release/v2.0.0` → `main` → tag `v2.0.0`

## Pending / next session ideas

- [ ] **Release 2.0** - see `RELEASE_2_0_PLAN.md` for full step-by-step plan
- [ ] **Add more YouTube content** - Blink, FLO, EVCS still have zero video coverage
- [ ] **Better web page coverage** - EVgo (246 chars) and PlugShare (133 chars) near-empty; retry with `wait_for`
- [ ] **HTTPS / custom domain** - self-signed cert live; full cert needs a domain
- [ ] **Export / report** - export RAG answers as PDF/DOCX
- [ ] **Email delivery** - wire SMTP for "Share Credentials" in Users tab

---

## How to check DB health

```python
& ".venv\Scripts\python.exe" -c "
import os, psycopg2
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path('config/.env'), override=True)
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute('SELECT source, COUNT(*) FROM document_chunks GROUP BY source')
[print(r) for r in cur.fetchall()]
conn.close()
"
```
