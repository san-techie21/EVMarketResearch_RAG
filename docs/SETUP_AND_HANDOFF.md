# Voltaic - Setup & Handoff Guide

Plain-English answers to: how to hand this to your friend, how to make it actually
work (not demo), where to add knowledge-base files, and how to manage accounts.

---

## The mental model (read this first)

The app has **three parts**:

| Part | What it is | Needs a key? |
|---|---|---|
| **Web** (`apps/web`) | The beautiful UI (login, chat, dashboards) | No |
| **API** (`apps/api`) | The brain: searches the knowledge base + calls the AI | **Yes - one LLM key** |
| **Database** (Postgres + pgvector) | Stores the knowledge as searchable vectors | No |

There are **two ways to run it**:

- **Demo mode** - just the Web part, with canned data. No backend, no key. This is
  what's live on Vercel now. Great for *showing* the experience.
- **Real mode** - all three parts running together. Add an LLM key + your documents
  and it answers real questions with citations. **This is what your friend wants.**

Embeddings (turning text into vectors) run **locally and free** - no key needed.
The **only** key required is one LLM key (Claude *or* OpenAI *or* DeepSeek/Groq/etc.).

---

## Q1. How do I give it to my friend?

It currently lives on **your** fork: `github.com/san-techie21/EVMarketResearch_RAG`
(branch `feature/v3-upgrade`). Pick whichever is easiest:

**Option A - He clones your repo (simplest).** Send him the link. He runs:
```bash
git clone -b feature/v3-upgrade https://github.com/san-techie21/EVMarketResearch_RAG
```
He never needs write access to your GitHub. He just runs it locally (see Q2).

**Option B - Transfer it to him.** Add him as a collaborator on your repo
(GitHub → Settings → Collaborators), or he forks it to his own account. Use this if
*he* will keep developing it.

**Option C - Zip it.** GitHub → Code → Download ZIP. Email it. (You lose git history,
but it runs the same.)

> You do **not** push your code "into his codebase." He gets a copy (clone/fork/zip)
> and runs it on his machine or his server. His API key and his data stay on his side
> - they never touch your repo.

---

## Q2. Will it work if he adds his AI API? (Yes - here's exactly how)

He needs **Docker Desktop** installed. Then, from the project folder:

```bash
cd infra
cp .env.example .env          # Windows: copy .env.example .env
```

Open `infra/.env` and set **one** LLM option (this is the only required step):
```ini
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...your key...
```
(or OpenAI / DeepSeek - the file shows all three options.)

Then start everything:
```bash
docker compose up -d --build
```

That's it. It builds and runs the database, API, and web app together. Open
**http://localhost:3000** and sign in (default: `admin` / `admin123` - change it, see Q4).

The first chat will be slow for ~30s while it downloads the local embedding model
once, then it's fast. **At this point it's a real, working RAG** - but the knowledge
base is empty until he adds data (Q3).

> "Will it work awesomely?" - Yes, once (a) his key is set and (b) there are documents
> to answer from. An LLM key alone with an empty knowledge base will just say "I don't
> have anything on that." Adding documents (Q3) is what makes it shine.

---

## Q3. Where do I add knowledge-base files (the RAG documents)?

There's a folder called **`knowledge_base/`** at the project root. Drop files in:

```
knowledge_base/
  product-manual.pdf
  faqs.md
  acme/                 <- optional sub-folder = a "group" tag
    competitor-brief.pdf
```
Supported: **`.txt`, `.md`, `.pdf`**. Sub-folder names become a group label so you can
filter by them later.

Then ingest them (turns them into searchable vectors):
```bash
docker compose exec api python pipeline/ingest_docs.py
```
(or, if running without Docker: `python pipeline/ingest_docs.py`)

Re-run any time you add files - duplicates are skipped. After this, the chat answers
from those documents, **with citations**.

*Optional EV/energy data:* this repo can also auto-collect EV app reviews and news.
That's the original use case - see `docs/V3_UPGRADE_PLAN.md`. For a generic knowledge
assistant, just use `knowledge_base/`.

---

## Q4. How do I manage accounts (the "analyst" login)?

Accounts live in **`config/users.yaml`** (passwords are stored hashed, never plain).
Manage them with a simple command:

```bash
# Add or update a user (password auto-generated and printed once):
python utils/add_user.py --email jane@acme.com --name "Jane Doe" --role admin

# Set a specific password:
python utils/add_user.py --email bob@acme.com --name "Bob" --role viewer --password "S3cret!"

# List everyone:
python utils/add_user.py --list

# Remove someone:
python utils/add_user.py --remove jane@acme.com
```

Roles: `superadmin`, `admin`, `viewer` (the app treats superadmin/admin as
privileged). **Change the default `admin/admin123` account on day one.**

After changing users while Docker is running, restart the API so it reloads them:
```bash
docker compose restart api
```

---

## Q5. How do I put it online (so others can use it, not just localhost)?

Three free pieces:
1. **Database** → [Neon](https://neon.tech) or [Supabase](https://supabase.com) (free
   Postgres with pgvector). Run the schema once: `infra/db/01_init.sql`.
2. **API** → [Render](https://render.com) or [Railway](https://railway.app) free tier.
   Deploy `apps/api` (it has a Dockerfile). Set `DATABASE_URL` + `LLM_API_KEY` in its
   env. Note its public URL, e.g. `https://voltaic-api.onrender.com`.
3. **Web** → [Vercel](https://vercel.com) (already set up). In the project's
   Settings → Environment Variables, set `NEXT_PUBLIC_API_URL` to the API's public URL,
   then redeploy. The UI flips from demo to live automatically.

That's the whole production path - no servers to manage, no domain required (you get
free `*.vercel.app` / `*.onrender.com` URLs).

---

## How the "demo vs real" switch works (one variable)

The web app checks `NEXT_PUBLIC_API_URL`:
- **empty** → demo mode (canned answers, no backend). This is the current Vercel deploy.
- **set to your API URL** → live mode (real retrieval + your LLM + your documents).

So the *same* UI is both the demo and the real product. Nothing to rewrite.

---

## Troubleshooting

- **"Couldn't reach the backend"** in chat → `NEXT_PUBLIC_API_URL` is wrong, or the API
  isn't running. Check `docker compose logs api`.
- **Chat says "I couldn't find anything"** → the knowledge base is empty. Do Q3.
- **`/health` shows `llm_key_set: false`** → the key isn't set in `infra/.env`
  (or you didn't restart: `docker compose restart api`).
- **Port already in use** → change `DB_PORT` / `API_PORT` / `WEB_PORT` in `infra/.env`.
- **First answer is slow** → one-time embedding-model download; subsequent calls are fast.
