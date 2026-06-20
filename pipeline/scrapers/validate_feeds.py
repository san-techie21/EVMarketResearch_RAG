"""
Feed health-check - validate every production RSS feed end-to-end.

Run this whenever news ingestion looks thin, or on a schedule, to catch feeds
that have gone dead, moved, or started blocking bots. It imports the live
`PUBLISHER_FEEDS` list from `news_feeds.py` so it always tests exactly what the
scraper uses (no drift).

For each feed it reports: HTTP reachability, parse success, entry count, newest
entry age, whether full text is available (content:encoded vs summary), and a
sample title. Exits non-zero if any feed is unreachable or stale (>14 days),
so it can gate CI / alerting.

Usage:
    python pipeline/scrapers/validate_feeds.py
    python pipeline/scrapers/validate_feeds.py --body      # also test body extraction
    python pipeline/scrapers/validate_feeds.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import requests
import feedparser

from news_feeds import PUBLISHER_FEEDS, fetch_full_body, UA  # noqa: E402

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})

STALE_DAYS = 14


def newest_age_days(entries) -> int | None:
    newest = None
    for e in entries:
        st = e.get("published_parsed") or e.get("updated_parsed")
        if st:
            dt = datetime(*st[:6], tzinfo=timezone.utc)
            if newest is None or dt > newest:
                newest = dt
    if newest is None:
        return None
    return (datetime.now(timezone.utc) - newest).days


def has_full_text(entries) -> tuple[bool, int]:
    has_ce, max_chars = False, 0
    for e in entries[:5]:
        if e.get("content"):
            has_ce = True
            for c in e["content"]:
                max_chars = max(max_chars, len(c.get("value", "")))
        max_chars = max(max_chars, len(e.get("summary", "")))
    return has_ce, max_chars


def check(name: str, url: str, test_body: bool) -> dict:
    row = {"name": name, "url": url, "ok": False, "entries": 0,
           "age_days": None, "full_text": "thin", "sample": "", "note": ""}
    try:
        r = SESSION.get(url, timeout=20)
        if r.status_code != 200:
            row["note"] = f"HTTP {r.status_code}"
            return row
        parsed = feedparser.parse(r.content)
        entries = parsed.entries or []
        row["entries"] = len(entries)
        if not entries:
            row["note"] = "0 entries"
            return row
        row["age_days"] = newest_age_days(entries)
        has_ce, max_chars = has_full_text(entries)
        row["full_text"] = "content:encoded" if has_ce else ("summary" if max_chars > 600 else "thin")
        row["sample"] = (entries[0].get("title") or "")[:60]
        row["ok"] = True
        if test_body and entries[0].get("link"):
            body, method = fetch_full_body(entries[0]["link"])
            row["body_chars"] = len(body)
            row["body_method"] = method
    except Exception as exc:
        row["note"] = f"{type(exc).__name__}: {exc}"
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", action="store_true", help="Also test full-body extraction (slower)")
    ap.add_argument("--json", help="Write machine-readable results to this path")
    args = ap.parse_args()

    print(f"Validating {len(PUBLISHER_FEEDS)} production feeds...\n")
    hdr = f"{'FEED':18} {'OK':3} {'#':>4} {'AGE':>4} {'FULLTEXT':>15}  SAMPLE"
    print(hdr); print("-" * len(hdr))

    rows = []
    for name, url, _hint in PUBLISHER_FEEDS:
        row = check(name, url, args.body)
        rows.append(row)
        flag = "Y" if row["ok"] else "."
        extra = ""
        if args.body and "body_chars" in row:
            extra = f"  body={row['body_chars']}({row['body_method']})"
        print(f"{name:18} {flag:3} {row['entries']:>4} "
              f"{str(row['age_days'] if row['age_days'] is not None else '-'):>4} "
              f"{row['full_text']:>15}  {row['sample']}{extra}  {row['note']}")
        time.sleep(0.3)

    dead = [r for r in rows if not r["ok"]]
    stale = [r for r in rows if r["ok"] and r["age_days"] is not None and r["age_days"] > STALE_DAYS]

    print(f"\nOK: {len(rows) - len(dead)}/{len(rows)}   dead: {len(dead)}   stale(>{STALE_DAYS}d): {len(stale)}")
    if dead:
        print("  DEAD:  " + ", ".join(f"{r['name']} ({r['note']})" for r in dead))
    if stale:
        print("  STALE: " + ", ".join(f"{r['name']} ({r['age_days']}d)" for r in stale))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, default=str)
        print(f"  results -> {args.json}")

    sys.exit(1 if (dead or stale) else 0)


if __name__ == "__main__":
    main()
