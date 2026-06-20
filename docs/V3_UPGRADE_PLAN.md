# EV Market Research RAG - v3 Upgrade Plan

> Fork: `san-techie21/EVMarketResearch_RAG` · branch `feature/v3-upgrade`
> Goal: take the existing (solid) v2 system and make it best-in-class - better
> data, better retrieval, hardened security, a modern Next.js UI, and a set of
> innovative competitive-intelligence features. Grounded in current (June 2026)
> best practices.

---

## Where v2 stands (honest baseline)

The v2 system is genuinely well-built, not "basic": pgvector RAG on DO Postgres
(~17.6k chunks), 5+ data sources, local embeddings (bge-small, 384-dim),
multi-user auth + roles, per-user chat history, an Admin Portal with a weekly
scheduler, query observability + RAGAs evaluation, and a deployed droplet
(nginx + systemd) with CI/CD + Terraform.

What actually held it back:
1. **News** - used Google News *search* RSS, whose `<link>`s are encoded redirect
   URLs, so full-body extraction silently failed → headline-only "news" chunks.
2. **Retrieval** - pure cosine top-K; minority sources (news/web/youtube) were
   drowned out and propped up with forced "guarantee" injectors (no relevance
   gate). No hybrid search, no reranking.
3. **UI** - Streamlit ceiling; login + chrome look generic.
4. **Security** - auth cookie secret committed in `users.yaml`, default creds,
   XSRF disabled, HTTP-only prod, a connection leak in `_get_kb_counts`.

---

## Target architecture (v3)

```
apps/
  api/      FastAPI - JWT auth, SSE streaming chat, search, insights, admin, stations
  web/      Next.js 15 (App Router) - premium login, streaming chat, dashboards
packages/
  rag/      retrieval core: hybrid (BM25+vector) + RRF + cross-encoder rerank
pipeline/   scrapers (improved) + processing + ingestion
infra/      docker-compose (pgvector + api + web), DB migrations, seed
```

Self-hostable: docker-compose brings up Postgres+pgvector, the API, and the web
app with no cloud dependency - so a fork can run the whole thing locally.

---

## Phases & status

| # | Phase | Status |
|---|---|---|
| 1 | **News overhaul** (free, full-text, multi-source) | ✅ DONE (tested live) |
| 2 | **Retrieval quality** (hybrid + RRF + rerank) | ✅ code complete (RRF unit-tested; live DB test pending Phase 4) |
| 3 | **Security hardening** | ✅ quick-wins done (cookie key→env, XSRF on, conn-leak fix) |
| 4 | **Self-host infra** (docker-compose + pgvector + migrations) | ✅ db tested live (schema + BM25 + vector + RRF verified on pgvector) |
| 6 | **Next.js frontend** (login, chat, dashboards) | ✅ built & verified (Aurora-Glass UI; demo-mode, Vercel-ready, build passes) |
| 5 | **FastAPI backend** (JWT auth, chat, stats; pluggable LLM) | ✅ built & tested + FULL STACK VERIFIED E2E in Docker (db+api+web all healthy; real ingest -> retrieval -> only the keyed LLM step pending the user's key) |
| 7 | **Innovative features** (below) | ◑ previewed in UI (sentiment-over-time, battlecards, station data) |

### Frontend (Phase 6) - "Aurora Glass"
- `apps/web` - Next.js 16 + React 19 + Tailwind v4 + Framer Motion. Runs
  standalone on demo data (`lib/mock.ts`) so it deploys to **Vercel** with no
  backend; swaps to live API via `NEXT_PUBLIC_API_URL`.
- Animated aurora background w/ cursor parallax (`aurora-background.tsx`),
  glassmorphic surfaces, spring motion, count-up KPIs, animated SVG sentiment
  chart, simulated streaming chat with cited sources. Production build passes;
  routes prerender static. Deploy: Vercel (root dir `apps/web`).

---

## Phase 1 - News overhaul ✅ (DONE, validated June 20 2026)

**Root cause fixed:** Google News RSS links are encoded redirects → trafilatura
got a consent page, not the article. Switched to **publisher-direct feeds**
(real article URLs) + GDELT.

New files:
- `pipeline/scrapers/news_feeds.py` - full-text, multi-source, relevance-matched
  scraper. Body strategy: `content:encoded` → trafilatura → browser-UA requests
  (recovers publishers that block bots, e.g. InsideEVs) → summary fallback.
  Word-boundary app matching (brand names don't match generic terms). Real
  `published_at` timestamps. Dedup by canonical URL + title. `_general` bucket.
  Optional GDELT (`--gdelt`, keyless, best-effort).
- `pipeline/scrapers/validate_feeds.py` - health-check tool; imports the live
  feed list, reports dead/stale feeds, exits non-zero for CI/alerting.

`pipeline/run_pipeline.py::read_news` updated to prepend headlines and carry
`published_at` + `publisher` metadata (for recency ranking + display).

**Validated feed list (17/17 live, all fresh):**
EV - Electrek, InsideEVs, Teslarati, TheDriven, ChargedEVs, CnEVPost, Electrive,
CleanTechnica, EVCentral. Energy/prosumer - PV Magazine USA, PV Magazine Global,
SolarPowerWorld, SolarBuilder, Energy-Storage.news, ESS-News, PV-Tech, Canary
Media. Dropped (dead): GreenCarReports (404), Autoblog (403).

**Verified end-to-end:** real June 2026 articles pulled with full bodies
(Electrek 3.6k chars, Teslarati 11k, Enphase/Energy-Storage 6.7k), correct
app matching, false positives rejected (`chargepoints` generic ≠ ChargePoint brand).

Run it:
```
python pipeline/scrapers/news_feeds.py --gdelt
python pipeline/scrapers/validate_feeds.py --body
python pipeline/run_pipeline.py --source news
```

---

## Phase 2 - Retrieval quality (next)

2026 best practice: two-stage **hybrid retrieval → rerank**.
- Add a Postgres `tsvector` column + GIN index for BM25 lexical search.
- Retrieve top-N by vector AND top-N by BM25, fuse with **Reciprocal Rank Fusion**.
- Re-score the fused pool with a local **cross-encoder reranker**
  (`BAAI/bge-reranker-v2-m3`), keep the best 8-12.
- Delete the `min_news`/`min_web`/`min_youtube` injector hacks - good minority
  chunks now rank up on merit.
- Fix the embedding instruction (bge query prefix should be asymmetric); a fresh
  fork re-embeds anyway, so optionally upgrade bge-small → bge-base/bge-m3.

## Phase 3 - Security
Cookie secret → env; re-enable XSRF; JWT auth in the API; TLS (Caddy/Let's
Encrypt or Cloudflare); fix the `_get_kb_counts` connection leak; rotate creds.

## Phases 4-6 - Infra + API + Web
docker-compose self-host; FastAPI (JWT, SSE streaming, sources, insights,
stations); Next.js 15 UI (premium login, streaming chat, source citations,
dashboards, export to PDF).

## Phase 7 - Innovative features (the "best of the best" layer)
- **Sentiment-over-time** per app/source (track perception shifts; charts).
- **Auto-generated battlecards** - one-click competitive brief per app.
- **Alerting** - notify on sentiment/volume spikes or new critical news.
- **Live EV station data** overlay via OpenChargeMap / NREL AFDC (free).
- **Scheduled email/PDF intelligence reports**.
- **Trend digest** - weekly "what changed across the market" summary.
```
