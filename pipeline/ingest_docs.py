"""
Ingest your own documents into the knowledge base.

Drop files into the `knowledge_base/` folder (optionally in sub-folders), then run:

    python pipeline/ingest_docs.py

Supported: .txt  .md  .pdf
- A file's parent sub-folder name becomes its `app_name` (so you can group docs);
  files placed directly in knowledge_base/ get app_name "general".
- Everything is chunked, embedded locally (bge-small, no API key), and upserted
  into the same `document_chunks` table the chat reads from. Re-running is safe
  (duplicates are skipped).

Examples of what to add: product docs, PDFs, competitor brochures, support FAQs,
meeting notes, exported reviews - anything you want the assistant to answer from.
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from run_pipeline import process_docs  # chunk -> embed -> upsert

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = REPO_ROOT / "knowledge_base"
SUPPORTED = {".txt", ".md", ".pdf"}


def read_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            log.warning("pypdf not installed - skipping %s (pip install pypdf)", path.name)
            return ""
        try:
            reader = PdfReader(str(path))
            return "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()
        except Exception as exc:
            log.warning("Failed to read PDF %s: %s", path.name, exc)
            return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception as exc:
        log.warning("Failed to read %s: %s", path.name, exc)
        return ""


def collect(folder: Path) -> list[dict]:
    docs = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        rel = path.relative_to(folder)
        app_name = rel.parts[0] if len(rel.parts) > 1 else "general"
        text = read_text(path)
        if len(text) < 30:
            log.info("  skip (empty/too short): %s", rel)
            continue
        docs.append({
            "source": "documents",
            "app_name": app_name,
            "category": "custom",
            "content": text,
            "metadata": {"file": str(rel), "title": path.stem},
        })
        log.info("  + %s  (%s, %d chars)", rel, app_name, len(text))
    return docs


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest local documents into the knowledge base")
    ap.add_argument("--dir", default=str(DEFAULT_DIR), help="Folder to ingest (default: knowledge_base/)")
    args = ap.parse_args()

    folder = Path(args.dir)
    if not folder.exists():
        folder.mkdir(parents=True, exist_ok=True)
        log.info("Created %s - drop your .txt/.md/.pdf files there and re-run.", folder)
        return

    log.info("Scanning %s ...", folder)
    docs = collect(folder)
    if not docs:
        log.warning("No supported documents found in %s", folder)
        return

    log.info("Ingesting %d documents ...", len(docs))
    process_docs(docs)
    log.info("Done. Ask the assistant about your documents in the chat.")


if __name__ == "__main__":
    main()
