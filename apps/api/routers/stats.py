"""Knowledge-base stats for the dashboard (counts by source, total, app count)."""
import os

import psycopg2
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
def stats():
    try:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT source, COUNT(*) FROM document_chunks GROUP BY source ORDER BY 2 DESC")
                by_source = [{"source": s, "count": c} for s, c in cur.fetchall()]
                cur.execute("SELECT COUNT(DISTINCT app_name) FROM document_chunks")
                apps = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM document_chunks")
                total = cur.fetchone()[0]
        finally:
            conn.close()
        return {"total": total, "apps": apps, "bySource": by_source}
    except Exception as exc:
        return {"total": 0, "apps": 0, "bySource": [], "error": str(exc)}
