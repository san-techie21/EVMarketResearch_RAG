"""
ingest_youtube_summaries.py

Reads structured YouTube summary .txt files from:
  data/raw/text/youtube_summaries/<app_name>/<video_id>_<slug>.txt

Chunks, embeds, and upserts into document_chunks with source='youtube'.
Safe to re-run - upsert.py deduplicates by (source, app_name, content).
"""

import json
import logging
import re
import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / "config" / ".env", override=True)

from pipeline.processing.chunker import chunk_text
from pipeline.processing.embedder import embed_texts
from pipeline.ingestion.upsert import upsert_chunks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SUMMARIES_DIR = ROOT / "data" / "raw" / "text" / "youtube_summaries"
YT_URL_RE = re.compile(r"https?://(?:www\.)?youtube\.com/watch\?v=([\w\-]+)")


def extract_header(text: str) -> tuple[str, str, str]:
    """
    Extract (title, video_id, url) from the top of a summary file.
    Title = first non-empty line (after stripping line-number prefixes).
    URL   = first YouTube URL found in the first 20 lines.
    """
    lines = text.splitlines()[:20]
    title = ""
    url = ""
    video_id = ""

    for line in lines:
        s = line.strip()
        if not s:
            continue
        m = YT_URL_RE.search(s)
        if m:
            url = m.group(0)
            video_id = m.group(1)
            continue
        if not title:
            title = s

    return title, video_id, url


def clean_content(text: str) -> str:
    """
    Light clean: strip markdown bold (**text**) markers and
    normalise whitespace.  Keep timestamp headers like [00:00:00]
    as they add useful structure context.
    """
    # Remove markdown bold
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    # Collapse 3+ blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def ingest_file(txt_path: Path, app_name: str) -> int:
    """Chunk, embed, and upsert one summary file. Returns chunks inserted."""
    raw = txt_path.read_text(encoding="utf-8")
    title, video_id, url = extract_header(raw)
    content = clean_content(raw)

    if not content:
        log.warning("Empty content in %s - skipping", txt_path.name)
        return 0

    chunks = chunk_text(content)
    if not chunks:
        return 0

    log.info("  %s → %d chunk(s)", txt_path.name, len(chunks))

    embeddings = embed_texts(chunks)

    records = [
        {
            "source": "youtube",
            "app_name": app_name,
            "content": chunk,
            "metadata": json.dumps({
                "title": title,
                "video_id": video_id,
                "url": url,
                "file": txt_path.name,
            }),
            "embedding": f"[{','.join(str(v) for v in emb)}]",
        }
        for chunk, emb in zip(chunks, embeddings)
    ]

    inserted = upsert_chunks(records)
    return inserted


def main():
    if not SUMMARIES_DIR.exists():
        log.error("Summaries directory not found: %s", SUMMARIES_DIR)
        sys.exit(1)

    total_files = 0
    total_chunks = 0

    app_dirs = sorted(d for d in SUMMARIES_DIR.iterdir() if d.is_dir())
    if not app_dirs:
        log.error("No app subdirectories found in %s", SUMMARIES_DIR)
        sys.exit(1)

    for app_dir in app_dirs:
        app_name = app_dir.name
        txt_files = sorted(app_dir.glob("*.txt"))
        if not txt_files:
            continue

        log.info("=== %s (%d files) ===", app_name, len(txt_files))
        for txt_path in txt_files:
            inserted = ingest_file(txt_path, app_name)
            total_chunks += inserted
            total_files += 1

    log.info("")
    log.info("Done. %d files processed, ~%d chunks upserted.", total_files, total_chunks)


if __name__ == "__main__":
    main()
