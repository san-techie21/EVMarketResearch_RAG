"""
Main pipeline runner. Reads all scraped raw data, chunks, embeds, and upserts to Postgres.

Usage:
    python pipeline/run_pipeline.py                     # process all sources
    python pipeline/run_pipeline.py --source google_play
    python pipeline/run_pipeline.py --source google_play --app chargepoint
"""
import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from processing.chunker import chunk_text
from processing.embedder import embed_texts
from ingestion.upsert import upsert_chunks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parents[1] / "data"
EMBED_BATCH = 128  # chunks to embed + upsert at once

APP_CATEGORIES: dict[str, str] = {
    # EV Charging
    "chargepoint":       "ev_charging",
    "evgo":              "ev_charging",
    "blink":             "ev_charging",
    "plugshare":         "ev_charging",
    "electrify_america": "ev_charging",
    "flo":               "ev_charging",
    "evcs":              "ev_charging",
    "shell_recharge":    "ev_charging",
    "tesla":             "ev_charging",
    # Prosumer / Home Energy
    "tesla_powerwall":   "prosumer",
    "enphase":           "prosumer",
    "solaredge":         "prosumer",
    "emporia":           "prosumer",
    "sense":             "prosumer",
    "sunpower":          "prosumer",
    "generac":           "prosumer",
    "span":              "prosumer",
}


# ---------------------------------------------------------------------------
# Source readers  (one function per scraper type)
# ---------------------------------------------------------------------------

def read_google_play(app_filter: str | None = None) -> list[dict]:
    """Yields raw document dicts from Google Play review JSON files."""
    docs = []
    base = DATA_DIR / "raw" / "text" / "google_play"
    for app_dir in sorted(base.iterdir()):
        if app_filter and app_dir.name != app_filter:
            continue
        reviews_file = app_dir / "reviews.json"
        if not reviews_file.exists():
            continue
        data = json.loads(reviews_file.read_text(encoding="utf-8"))
        for r in data.get("reviews", []):
            content = (r.get("content") or "").strip()
            if not content:
                continue
            docs.append({
                "source":    "google_play",
                "app_name":  app_dir.name,
                "category":  APP_CATEGORIES.get(app_dir.name, "ev_charging"),
                "content":   content,
                "metadata": {
                    "score":      r.get("score"),
                    "date":       r.get("at"),
                    "thumbs_up":  r.get("thumbsUpCount"),
                    "review_id":  r.get("reviewId"),
                },
            })
    log.info("Google Play: loaded %d reviews", len(docs))
    return docs


def read_app_store(app_filter: str | None = None) -> list[dict]:
    """Yields raw document dicts from App Store review JSON files."""
    docs = []
    base = DATA_DIR / "raw" / "text" / "app_store"
    for app_dir in sorted(base.iterdir()):
        if app_filter and app_dir.name != app_filter:
            continue
        reviews_file = app_dir / "reviews.json"
        if not reviews_file.exists():
            continue
        data = json.loads(reviews_file.read_text(encoding="utf-8"))
        for r in data.get("reviews", []):
            title   = (r.get("title")   or "").strip()
            content = (r.get("content") or "").strip()
            text    = f"{title}. {content}".strip(". ") if title else content
            if not text:
                continue
            docs.append({
                "source":    "app_store",
                "app_name":  app_dir.name,
                "category":  APP_CATEGORIES.get(app_dir.name, "ev_charging"),
                "content":   text,
                "metadata": {
                    "score":     r.get("score"),
                    "date":      r.get("date"),
                    "version":   r.get("version"),
                    "review_id": r.get("reviewId"),
                },
            })
    log.info("App Store: loaded %d reviews", len(docs))
    return docs


def read_youtube(app_filter: str | None = None) -> list[dict]:
    """
    Reads YouTube summary .txt files from data/raw/text/youtube_summaries/.

    Expected file format (header lines followed by a blank line, then body):
        Title:    <video title>
        Video ID: <youtube video id>
        URL:      https://www.youtube.com/watch?v=...
        App:      <app_name>   (optional - folder name is used as app_name)

        <full summary / transcript body>
    """
    docs = []
    base = DATA_DIR / "raw" / "text" / "youtube_summaries"
    if not base.exists():
        log.warning("youtube_summaries/ directory not found - nothing to ingest")
        return docs

    for app_dir in sorted(base.iterdir()):
        if not app_dir.is_dir():
            continue
        if app_filter and app_dir.name != app_filter:
            continue
        for txt_file in sorted(app_dir.glob("*.txt")):
            raw = txt_file.read_text(encoding="utf-8").strip()
            if not raw:
                continue

            # Parse header key: value lines until first blank line
            lines = raw.splitlines()
            meta: dict = {}
            body_start = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped:
                    body_start = i + 1
                    break
                if ":" in stripped:
                    key, _, val = stripped.partition(":")
                    meta[key.strip().lower().replace(" ", "_")] = val.strip()

            body = "\n".join(lines[body_start:]).strip() or raw
            docs.append({
                "source":    "youtube",
                "app_name":  app_dir.name,
                "category":  APP_CATEGORIES.get(app_dir.name, "ev_charging"),
                "content":   body,
                "metadata": {
                    "title":    meta.get("title", ""),
                    "video_id": meta.get("video_id", ""),
                    "url":      meta.get("url", ""),
                    "file":     txt_file.name,
                },
            })

    log.info("YouTube summaries: loaded %d files", len(docs))
    return docs


def read_news(app_filter: str | None = None) -> list[dict]:
    """Yields raw document dicts from news JSON files (news_feeds.py / news_rss.py).

    The v3 scraper (news_feeds.py) provides full bodies + real `published_at`
    timestamps + publisher names; the title is prepended to the body so the
    chunk is self-describing for retrieval. Legacy files (title+description
    only) still work via the fallback.
    """
    docs = []
    base = DATA_DIR / "raw" / "text" / "news"
    if not base.exists():
        log.warning("News data directory not found - run news_feeds.py first")
        return docs
    for app_dir in sorted(base.iterdir()):
        if app_filter and app_dir.name != app_filter:
            continue
        # "_general" folder maps to app_name="general"
        app_name = "general" if app_dir.name == "_general" else app_dir.name
        articles_file = app_dir / "articles.json"
        if not articles_file.exists():
            continue
        data = json.loads(articles_file.read_text(encoding="utf-8"))
        for a in data.get("articles", []):
            title = (a.get("title") or "").strip()
            desc  = (a.get("description") or "").strip()
            body  = (a.get("body") or "").strip()
            # Prefer full body; prepend the headline so the chunk is self-describing.
            if len(body) > 200:
                text = f"{title}\n\n{body}" if title and not body.startswith(title) else body
            else:
                text = f"{title}. {desc}".strip(". ") if desc else title
            if not text:
                continue
            docs.append({
                "source":    "news",
                "app_name":  app_name,
                "category":  a.get("category") or APP_CATEGORIES.get(app_name, "ev_charging"),
                "content":   text,
                "metadata": {
                    "title":        title,
                    "source_name":  a.get("publisher") or a.get("source"),
                    "published":    a.get("published"),
                    "published_at": a.get("published_at"),
                    "link":         a.get("link"),
                    "query":        a.get("query"),
                },
            })
    log.info("News: loaded %d articles", len(docs))
    return docs


def read_web_pages(app_filter: str | None = None) -> list[dict]:
    """Yields raw document dicts from Firecrawl web page JSON files."""
    docs = []
    base = DATA_DIR / "raw" / "text" / "web_pages"
    if not base.exists():
        log.warning("Web pages data directory not found - run the web pages scraper first")
        return docs
    for app_dir in sorted(base.iterdir()):
        if app_filter and app_dir.name != app_filter:
            continue
        pages_file = app_dir / "pages.json"
        if not pages_file.exists():
            continue
        data = json.loads(pages_file.read_text(encoding="utf-8"))
        for p in data.get("pages", []):
            content = (p.get("content") or "").strip()
            if not content:
                continue
            # Strip common cookie-consent / nav boilerplate that Firecrawl captures
            # before the actual page content (e.g. Blink, Shell Recharge sites).
            _BOILERPLATE_PREFIXES = (
                "we value your privacy",
                "this site uses cookies",
                "by clicking",
                "skip to main content",
                "skip to content",
                "![revisit consent",
            )
            cl = content.lower()
            for bp in _BOILERPLATE_PREFIXES:
                if cl.startswith(bp):
                    # Find the first real paragraph (2+ newlines after the boilerplate)
                    cut = content.find("\n\n", 300)
                    if cut > 0:
                        content = content[cut:].strip()
                    break
            if len(content) < 100:   # skip pages that are essentially empty after cleaning
                continue
            docs.append({
                "source":    "web_pages",
                "app_name":  app_dir.name,
                "category":  APP_CATEGORIES.get(app_dir.name, "ev_charging"),
                "content":   content,
                "metadata": {
                    "url":         p.get("url"),
                    "title":       p.get("title"),
                    "description": p.get("description"),
                },
            })
    log.info("Web pages: loaded %d pages", len(docs))
    return docs


SOURCE_READERS = {
    "google_play": read_google_play,
    "app_store":   read_app_store,
    "news":        read_news,
    "youtube":     read_youtube,
    "web_pages":   read_web_pages,
}


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def process_docs(docs: list[dict]) -> None:
    """Chunk → embed → upsert a list of raw documents."""
    # Build flat list of chunks with metadata
    all_chunks = []
    for doc in docs:
        for chunk_text_val in chunk_text(doc["content"]):
            all_chunks.append({
                "source":    doc["source"],
                "app_name":  doc["app_name"],
                "category":  doc.get("category", "ev_charging"),
                "content":   chunk_text_val,
                "metadata":  json.dumps(doc["metadata"]),
                "embedding": None,
            })

    log.info("Total chunks to embed: %d", len(all_chunks))

    total_inserted = 0
    for i in range(0, len(all_chunks), EMBED_BATCH):
        batch = all_chunks[i : i + EMBED_BATCH]
        texts = [c["content"] for c in batch]

        vectors = embed_texts(texts)
        for chunk, vec in zip(batch, vectors):
            chunk["embedding"] = vec

        inserted = upsert_chunks(batch)
        total_inserted += inserted
        log.info("  Batch %d/%d - upserted %d chunks (total: %d)",
                 i // EMBED_BATCH + 1,
                 -(-len(all_chunks) // EMBED_BATCH),
                 inserted,
                 total_inserted)

    log.info("Done. Total upserted: %d", total_inserted)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=list(SOURCE_READERS.keys()),
                        help="Process only this source (default: all)")
    parser.add_argument("--app", help="Filter to a specific app name")
    args = parser.parse_args()

    sources = [args.source] if args.source else list(SOURCE_READERS.keys())

    all_docs = []
    for source in sources:
        reader = SOURCE_READERS[source]
        kwargs = {}
        if args.app:
            kwargs["app_filter"] = args.app
        all_docs.extend(reader(**kwargs))

    if not all_docs:
        log.warning("No documents found. Check that scrapers have been run.")
        return

    log.info("Processing %d total documents...", len(all_docs))
    process_docs(all_docs)


if __name__ == "__main__":
    main()
