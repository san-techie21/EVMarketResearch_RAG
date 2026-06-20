# EV Market Research RAG System - Full Project Log

> Last updated: 2026-06-07
> A complete record of everything built, every decision made, and all problems solved across all sessions.

---

## What This Project Is

A **Retrieval-Augmented Generation (RAG)** knowledge base for competitive intelligence research on **North American EV charging apps**. It collects data from five source types, embeds it with a local model, stores vectors in pgvector on DigitalOcean Postgres, and exposes a multi-user chat interface powered by Claude.

**Target apps:** ChargePoint, EVgo, Blink, PlugShare, Electrify America, FLO, EVCS, Shell Recharge, Tesla

---

## System Architecture

| Layer | Technology | Notes |
|---|---|---|
| Local machine | Windows (pipeline runs here) | All scraping + embedding done locally |
| Vector DB | pgvector on DO Managed Postgres (blr1) | `ev-research-db` cluster |
| Embedding model | BAAI/bge-small-en-v1.5 | Local CPU, 384 dims, already downloaded |
| LLM | claude-sonnet-4-6 | Via Anthropic API |
| Chat UI | Streamlit + streamlit-authenticator | Multi-user with session persistence |
| Cloud hosting | DigitalOcean Droplet | s-1vcpu-2gb, Ubuntu 22.04, blr1, IP: 168.144.26.72 |
| Reverse proxy | nginx | Port 80 → 8501, WebSocket support |
| Process manager | systemd | Auto-restarts on crash/reboot |

---

## Live URLs

| Environment | URL |
|---|---|
| Local dev | http://localhost:8501 |
| Production (cloud) | http://168.144.26.72 |

---

## Knowledge Base (Postgres) - Current State

**11,322 chunks total** in `document_chunks` table on DO Managed Postgres (blr1)

| Source | Chunks | Description |
|---|---|---|
| google_play | 5,973 | User reviews from Google Play Store |
| app_store | 3,687 | User reviews from Apple App Store |
| news | 1,443 | News articles and press coverage (RSS) |
| youtube | 107 | Video summaries/transcripts (manually curated) |
| web_pages | 112 | Official company website content (Firecrawl) |
| **TOTAL** | **11,322** | |

Each chunk: 512 tokens, 64-token overlap, `tiktoken cl100k_base`

---

## Complete File Structure

```
C:\EVMarketResearch\
├-- config/
│   ├-- .env                           LIVE - all credentials set
│   └-- users.yaml                     bcrypt-hashed user credentials
├-- pipeline/
│   ├-- scrapers/
│   │   ├-- google_play.py             DONE - scrapes Google Play reviews
│   │   ├-- app_store.py               DONE - scrapes App Store reviews
│   │   ├-- news_rss.py                DONE - RSS feed scraper
│   │   ├-- youtube.py                 DONE (yt-dlp) - IP-rate-limited, don't re-run
│   │   ├-- web_pages.py               DONE (Firecrawl) - official website scraper
│   │   ├-- parse_transcripts.py       DONE - manual YouTube transcript parser
│   │   └-- ingest_youtube_summaries.py DONE - ingests from youtube_summaries/ folder
│   ├-- processing/
│   │   ├-- chunker.py                 DONE - 512 tok / 64 overlap
│   │   └-- embedder.py                DONE - bge-small-en-v1.5, 384 dims
│   └-- ingestion/
│       └-- upsert.py                  DONE
├-- rag/
│   ├-- retriever.py                   DONE - embed → pgvector → Claude
│   ├-- api/query.py                   DONE - FastAPI POST /query
│   └-- chat_ui/
│       ├-- app.py                     DONE - Streamlit multi-user UI
│       └-- session_db.py              DONE - Postgres chat session persistence
├-- utils/
│   └-- manage_users.py                DONE - bcrypt password hash generator
└-- data/raw/text/
    ├-- google_play/   7 app folders, reviews.json each
    ├-- app_store/     9 app folders, reviews.json each
    ├-- news/          9 app folders + _general, articles.json each
    ├-- youtube/       6 app folders, transcripts.json each (21 videos)
    ├-- youtube_summaries/             NEW dedicated folder for curated summaries
    │   ├-- chargepoint/  (3 .txt files)
    │   ├-- evgo/         (2 .txt files)
    │   ├-- tesla/        (4 .txt files)
    │   ├-- plugshare/    (2 .txt files)
    │   ├-- shell_recharge/ (3 .txt files)
    │   └-- general/      (1 .txt file)
    └-- web_pages/     9 app folders, pages.json each (25 pages)
```

---

## Everything Built - Session by Session

### Session 1 - Foundation
- Set up DigitalOcean Managed Postgres with pgvector extension
- Built Google Play scraper → collected reviews for 7 apps
- Built App Store scraper → collected reviews for 9 apps
- Built News RSS scraper → collected articles for 9 apps + general
- Set up chunker (512 tok / 64 overlap) and embedder (bge-small-en-v1.5)
- Built upsert pipeline and loaded first ~11k chunks
- Built `rag/retriever.py` - core embed→search→Claude logic
- Built FastAPI endpoint at `rag/api/query.py`
- Built first Streamlit UI at `rag/chat_ui/app.py`

**Critical fix discovered:** `load_dotenv` must use `override=True` in `rag/retriever.py` - `ANTHROPIC_API_KEY` was already set to empty string in Windows system environment. Without override, the empty value wins and all Claude API calls fail with auth error.

### Session 2 - Web Pages + YouTube
- Built Firecrawl-based web page scraper → 25 pages scraped, 112 chunks
- Discovered some pages near-empty (EVgo: 246 chars, PlugShare: 133 chars) - Firecrawl limitation
- Built YouTube scraper (`youtube.py` using yt-dlp) - immediately IP-rate-limited by YouTube
- Manually curated 21 YouTube transcripts and parsed them via `parse_transcripts.py`
- Loaded YouTube transcripts into Postgres (original batch, later replaced)

### Session 3 - YouTube Retrieval Debugging + UI
**Problem:** YouTube chunks weren't being retrieved - RAG responses claimed "no YouTube data in knowledge base"

**Root causes found and fixed:**
1. SYSTEM_PROMPT only listed 3 source types (not youtube/web_pages) → Claude didn't know to use them
2. Streamlit slider was hardcoded to pass `top_k=8` directly, ignoring the `TOP_K=12` env var
3. Stale `__pycache__` bytecode causing old code to run after edits
4. `YT_MIN_SCORE=0.60` was too high - YouTube chunks scored 0.563-0.587 (just below threshold)

**Fixes applied to `rag/retriever.py`:**
- Lowered `YT_MIN_SCORE` to `0.50`
- Added `_YT_KEYWORDS` set - auto-detects YouTube-focused queries and bumps `min_youtube` from 2 → 6
- Added `retrieve_by_source()` function for explicit source filtering
- Raised default `TOP_K` to 12
- Added SYSTEM_PROMPT entries for all 5 source types

**New YouTube content pipeline:**
- Created `data/raw/text/youtube_summaries/` as dedicated folder for curated video content
- Built `pipeline/scrapers/ingest_youtube_summaries.py` to read `.txt` files from that folder
- File format: header block with `Title:`, `Video ID:`, `URL:`, then content body
- Deleted all old YouTube chunks from Postgres, re-ingested from new summaries folder
- Result: 107 YouTube chunks (up from ~66 raw transcript chunks)

**Added to Streamlit UI:**
- Source filter dropdown: All / youtube / google_play / app_store / news / web_pages

### Session 4 - Auth + Session Persistence + Token Display + UI Redesign

**User authentication:**
- Added `streamlit-authenticator` library with bcrypt password hashing
- Credentials stored in `config/users.yaml` (bcrypt hashes, never plain text)
- `utils/manage_users.py` - helper script to generate hashes; edit `USERS` dict, run, copy output to yaml
- Login page replaces app until authenticated; cookie-based session (30-day expiry)

**Default users:**
| Username | Password | Display Name |
|---|---|---|
| admin | admin123 | Admin |
| user1 | changeme1 | User1 |
| user2 | changeme2 | User2 |

**Per-user chat session persistence:**
- Created `rag/chat_ui/session_db.py`
- New Postgres table: `chat_sessions` (username, session_id UUID, title, messages JSONB, timestamps)
- Sidebar shows past chats per user, ordered by most recently updated
- "New Chat" button creates fresh session
- Session title auto-set from first question (truncated to 60 chars)
- `ensure_table()` called on startup - idempotent, safe

**Token usage display:**
- `generate_answer()` in `retriever.py` now returns `tuple[str, dict]`
- Usage dict: `input_tokens`, `output_tokens`, `total_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`
- Displayed below each assistant response as small styled text

**Major UI redesign (comprehensive CSS overhaul):**
- Dark sidebar: `#0f0f1a` background
- Hidden Streamlit default chrome (hamburger menu, footer, deploy button)
- Font hierarchy fixed:
  - Chat H1: 1.15rem (was too large)
  - Chat H2: 1.0rem
  - Chat H3: 0.92rem
  - Body/paragraph text: 0.92rem (was too tiny)
- Sidebar hierarchy: branding → New Chat button → past chats list → KB stats expander → Search Settings expander → user avatar at bottom
- Top bar: app title left + `st.popover("···")` right
  - Popover shows display name, @username, divider, Sign out button
  - Replaces old username badge in top-left corner

**Bug fixed:** `NameError: name 'MODEL' is not defined` - `MODEL` was defined in `retriever.py` but not imported into `app.py`. Added `MODEL` to the import line.

### Session 5 - DigitalOcean Deployment

**Droplet details:**
- Provider: DigitalOcean
- Size: s-1vcpu-2gb ($12/mo)
- Region: blr1 (Bangalore)
- OS: Ubuntu 22.04 LTS
- IP: 168.144.26.72
- Droplet ID: 575812108

**SSH key:**
- Generated: `C:\Users\Admin\.ssh\ev_research_do` (ed25519)
- Public key ID on DO: 56921441
- Added to droplet at creation

**Server setup steps completed:**
1. Created directory structure at `/opt/ev-research/`
2. Uploaded all code files via `scp`
3. Discovered Ubuntu 22.04 apt had Python 3.11.0rc1 (release candidate!) - caused `torch` `AttributeError: sys.get_int_max_str_digits` 
4. Fixed by using Python 3.10.12 (stable): `apt install python3.10-venv`, recreated venv
5. Installed all packages without version pins (avoiding Windows-pinned version conflicts):
   - streamlit 1.58.0, anthropic 0.107.0, psycopg2-binary, sentence-transformers
   - tiktoken, bcrypt, streamlit-authenticator, python-dotenv
6. Smoke test passed: all imports OK, DB URL set, Anthropic key set
7. Created systemd service `/etc/systemd/system/ev-research.service`
8. Configured nginx reverse proxy `/etc/nginx/sites-available/ev-research` (port 80 → 8501, WebSocket headers)
9. Enabled and started both services - both running
10. HTTP health check: 200 OK on both port 8501 and port 80

**Server management commands:**
```bash
# SSH into server
ssh -i "C:\Users\Admin\.ssh\ev_research_do" root@168.144.26.72

# View app logs
journalctl -u ev-research -n 50 -f

# Restart app (after code changes)
systemctl restart ev-research

# Check status
systemctl status ev-research
systemctl status nginx

# Upload a changed file
scp -i "C:\Users\Admin\.ssh\ev_research_do" rag/chat_ui/app.py root@168.144.26.72:/opt/ev-research/rag/chat_ui/app.py
```

---

## All Credentials (where they live)

| Credential | File | Notes |
|---|---|---|
| DATABASE_URL | config/.env | Pipeline Postgres user |
| DATABASE_ADMIN_URL | config/.env | doadmin Postgres user |
| ANTHROPIC_API_KEY | config/.env | claude-sonnet-4-6 |
| YOUTUBE_API_KEY | config/.env | YouTube Data API v3 |
| FIRECRAWL_API_KEY | config/.env | Free tier, ~450 credits remaining |
| DO_TOKEN | config/.env | DigitalOcean API token |
| SSH private key | C:\Users\Admin\.ssh\ev_research_do | ed25519, DO key ID 56921441 |
| App passwords | config/users.yaml | bcrypt hashed |

---

## Key Technical Gotchas (Hard-Won Knowledge)

1. **`load_dotenv` must use `override=True`** in `rag/retriever.py` - `ANTHROPIC_API_KEY` was pre-set to empty string in Windows system env. Without override, the empty value wins → auth failure.

2. **Clear `__pycache__` on import errors** - stale bytecode causes old code to run after edits:
   ```powershell
   Remove-Item -Recurse -Force rag\__pycache__, rag\chat_ui\__pycache__, rag\api\__pycache__
   ```

3. **YouTube scraper is IP-rate-limited** - `youtube.py` is correct but YouTube blocks transcript access from this IP. Don't re-run without ~1hr wait. The 21 video transcripts were added manually.

4. **YouTube chunks are a tiny minority** (107 / 11,322 = 0.9%) - pure cosine top-K always drowns them out. Fix: `min_youtube` guarantee logic + `YT_MIN_SCORE=0.50` + keyword auto-detection in `retriever.py`.

5. **Model name is `claude-sonnet-4-6`** - not `claude-3-5-sonnet` or `claude-sonnet-4-20250514` (retired).

6. **Python version on Ubuntu** - `apt install python3.11` gives 3.11.0rc1 (release candidate), which breaks `torch`. Always use `python3.10` on Ubuntu 22.04.

7. **Do NOT re-run** scrapers or `setup_db.py` / `update_schema.py` - data is live in production.

8. **Do NOT change** embedding model or vector dimensions - 384-dim is baked into all 11,322 existing chunks.

9. **Streamlit WebSocket** - nginx must pass `Upgrade` and `Connection: upgrade` headers, or the Streamlit app shows a blank page / disconnects immediately.

---

## How to Run Locally

```bash
cd C:\EVMarketResearch
.venv\Scripts\streamlit run rag/chat_ui/app.py
# Opens at http://localhost:8501
```

## How to Add More YouTube Content

1. Create a `.txt` file in `data/raw/text/youtube_summaries/<app_name>/`
2. File format:
   ```
   Title: [Video Title]
   Video ID: [YouTube video ID]
   URL: https://www.youtube.com/watch?v=[video_id]
   App: [app_name]
   
   [Content / summary / transcript here]
   ```
3. Run: `python pipeline/run_pipeline.py --source youtube`
   (This calls `ingest_youtube_summaries.py`, not the rate-limited `youtube.py`)

## How to Add/Change Users

1. Edit `USERS` dict in `utils/manage_users.py`
2. Run: `python utils/manage_users.py`
3. Copy the printed YAML block into `config/users.yaml`
4. On server: re-upload the yaml file and restart the app

## How to Check DB Health

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

---

## Pending / Next Session Ideas

- [ ] **Add more YouTube content** - 3 apps still have no video coverage: Blink, FLO, EVCS
- [ ] **Better web page coverage** - Firecrawl returned near-empty pages for EVgo and PlugShare. Retry with different URLs or `wait_for` parameter
- [ ] **Export / report feature** - export RAG conversation as a formatted PDF/DOCX report
- [ ] **HTTPS / domain** - currently HTTP only (port 80). Could add Let's Encrypt SSL via certbot if a domain is purchased
- [ ] **More Google Play / App Store reviews** - could expand scrape depth for newer reviews
- [ ] **Prompt tuning** - system prompt could be improved with more specific instructions for comparison queries
- [ ] **Cost optimization** - token usage is visible per query; could experiment with prompt compression or caching for repeated questions

---

## Retriever Logic Summary (`rag/retriever.py`)

```
retrieve(question, app_filter, top_k=12, min_youtube=2)
  └-- embed question (bge-small-en-v1.5, local)
  └-- cosine similarity search in pgvector (top_k chunks)
  └-- if no app_filter and min_youtube > 0:
        check YouTube representation; fetch extras if short
        only include extras with score >= 0.50
  └-- if "youtube/video/transcript" in question: bump min_youtube to 6
  └-- sort all chunks by score DESC → return

retrieve_per_app(question, n_per_app=3)
  └-- runs one query per app (9 apps), fetches top n_per_app each
  └-- used for comparison mode (guarantees all-app coverage)

retrieve_by_source(question, source, top_k=12)
  └-- filters WHERE source = 'youtube' (or any source)
  └-- used by explicit source filter dropdown in UI

generate_answer(question, chunks) → (answer_text, usage_dict)
  └-- formats chunks as context with [source | app | score] headers
  └-- calls claude-sonnet-4-6 with SYSTEM_PROMPT + context + question
  └-- returns answer text + token usage dict
```

---

## Chat Session DB Schema

```sql
CREATE TABLE chat_sessions (
    id          SERIAL PRIMARY KEY,
    username    TEXT NOT NULL,
    session_id  TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL DEFAULT 'New Chat',
    messages    JSONB NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chat_sessions_username ON chat_sessions(username);
```

Messages JSONB format:
```json
[
  {"role": "user", "content": "What do users say about ChargePoint reliability?"},
  {"role": "assistant", "content": "...", "sources": [...], "usage": {...}}
]
```
