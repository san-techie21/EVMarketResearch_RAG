"""
iOS App Store scraper using Apple's public iTunes RSS + Search APIs.
No API key required.

Usage:
    python pipeline/scrapers/app_store.py
    python pipeline/scrapers/app_store.py --app chargepoint evgo

Output:
    data/raw/text/app_store/<app_name>/reviews.json
    data/raw/metadata/app_store/<app_name>/app_info.json
"""
import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Target apps  (iTunes app ID)
# ---------------------------------------------------------------------------
APPS = {
    # EV Charging
    "chargepoint":       356866743,
    "evgo":              1281660968,
    "blink":             1612678852,
    "plugshare":         421788217,
    "electrify_america": 1458030456,
    "flo":               808395252,
    "evcs":              1643179789,
    "shell_recharge":    1410234033,
    "tesla":             582007913,
    # Prosumer / Home Energy
    "tesla_powerwall":   582007913,   # Tesla app (covers Powerwall)
    "enphase":           787415770,   # Enphase Enlighten
    "solaredge":         1473952773,  # mySolarEdge
    "emporia":           1449205453,  # Emporia Energy
    "sense":             1024626982,  # Sense Home
    "sunpower":          1504718150,  # SunStrong Connect (SunPower rebranded)
    "generac":           1470592171,  # Generac PWRview
    "span":              1501617838,  # SPAN Home
}

COUNTRY      = "us"
MAX_PAGES    = 10       # iTunes RSS max = 10 pages × 50 reviews = 500 per app
SLEEP_SECS   = 1.5

BASE_DIR  = Path(__file__).parents[2] / "data"
TEXT_DIR  = BASE_DIR / "raw" / "text" / "app_store"
META_DIR  = BASE_DIR / "raw" / "metadata" / "app_store"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (compatible; ev-research-bot/1.0)"})


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _get_json(url: str) -> dict:
    resp = SESSION.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_app_info(app_id: int) -> dict | None:
    url = f"https://itunes.apple.com/lookup?id={app_id}&country={COUNTRY}"
    data = _get_json(url)
    results = data.get("results", [])
    if not results:
        return None
    r = results[0]
    return {
        "appId":           app_id,
        "bundleId":        r.get("bundleId"),
        "title":           r.get("trackName"),
        "developer":       r.get("artistName"),
        "score":           r.get("averageUserRating"),
        "ratingCount":     r.get("userRatingCount"),
        "description":     r.get("description"),
        "version":         r.get("version"),
        "releaseNotes":    r.get("releaseNotes"),
        "genres":          r.get("genres"),
        "price":           r.get("price"),
        "scraped_at":      datetime.now(timezone.utc).isoformat(),
    }


def fetch_reviews(app_id: int) -> list[dict]:
    all_reviews = []
    for page in range(1, MAX_PAGES + 1):
        url = (
            f"https://itunes.apple.com/rss/customerreviews/"
            f"page={page}/id={app_id}/sortby=mostrecent/json?country={COUNTRY}"
        )
        try:
            data = _get_json(url)
        except Exception as exc:
            log.warning("  Page %d failed: %s", page, exc)
            break

        entries = data.get("feed", {}).get("entry", [])
        if not entries:
            break

        # First entry on page 1 is app info, not a review
        if page == 1 and entries and "im:name" in entries[0]:
            entries = entries[1:]

        for e in entries:
            all_reviews.append({
                "reviewId":  e.get("id", {}).get("label"),
                "title":     e.get("title", {}).get("label"),
                "content":   e.get("content", {}).get("label"),
                "score":     int(e.get("im:rating", {}).get("label", 0)),
                "version":   e.get("im:version", {}).get("label"),
                "author":    e.get("author", {}).get("name", {}).get("label"),
                "date":      e.get("updated", {}).get("label"),
                "voteSum":   e.get("im:voteSum", {}).get("label"),
                "voteCount": e.get("im:voteCount", {}).get("label"),
            })

        log.info("  page %d/%d - %d reviews so far", page, MAX_PAGES, len(all_reviews))
        time.sleep(SLEEP_SECS)

    return all_reviews


def scrape_app(name: str, app_id: int) -> None:
    log.info("=== Scraping %s (id=%d) ===", name, app_id)

    text_dir = TEXT_DIR / name
    meta_dir = META_DIR / name
    text_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    # App info
    try:
        info = fetch_app_info(app_id)
        if not info:
            log.warning("  App id=%d not found on App Store - skipping", app_id)
            return
        meta_path = meta_dir / "app_info.json"
        meta_path.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("  App info saved (rating: %.1f, ratings: %s)",
                 info.get("score") or 0, info.get("ratingCount") or "?")
    except Exception as exc:
        log.error("  Failed to fetch app info for %s: %s", name, exc)
        return

    # Reviews
    try:
        revs = fetch_reviews(app_id)
        reviews_path = text_dir / "reviews.json"
        reviews_path.write_text(
            json.dumps({"app": name, "app_id": app_id, "count": len(revs), "reviews": revs},
                       indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        log.info("  %d reviews saved", len(revs))
    except Exception as exc:
        log.error("  Failed to fetch reviews for %s: %s", name, exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape iOS App Store reviews for EV charging apps")
    parser.add_argument("--app", nargs="+", choices=list(APPS.keys()),
                        help="Scrape specific apps only (default: all)")
    args = parser.parse_args()

    targets = {k: v for k, v in APPS.items() if not args.app or k in args.app}
    log.info("Scraping %d app(s): %s", len(targets), ", ".join(targets))

    for name, app_id in targets.items():
        try:
            scrape_app(name, app_id)
        except Exception as exc:
            log.error("Unexpected error scraping %s: %s", name, exc)
        time.sleep(SLEEP_SECS)

    log.info("Done.")


if __name__ == "__main__":
    main()
