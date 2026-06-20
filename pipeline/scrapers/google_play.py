"""
Google Play Store scraper.
Fetches app info + reviews for all target EV charging apps.

Usage:
    python pipeline/scrapers/google_play.py
    python pipeline/scrapers/google_play.py --app chargepoint evgo

Output:
    data/raw/text/google_play/<app_name>/reviews.json
    data/raw/metadata/google_play/<app_name>/app_info.json
"""
import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from google_play_scraper import app as gp_app
from google_play_scraper import reviews as gp_reviews
from google_play_scraper.exceptions import NotFoundError

load_dotenv(Path(__file__).parents[2] / "config" / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Target apps  (app_id = Google Play package name)
# ---------------------------------------------------------------------------
APPS = {
    # EV Charging
    "chargepoint":    "com.coulombtech",
    "evgo":           "com.driivz.mobile.android.evgo.driver",
    "blink":          "com.blinknetwork.mobile2",
    "plugshare":      "com.xatori.Plugshare",
    "evcs":           "org.evcs.android",
    "shell_recharge": "com.shell.sitibv.motorist.america",
    "tesla":          "com.teslamotors.tesla",
    # Prosumer / Home Energy
    "tesla_powerwall": "com.teslamotors.tesla",      # same Tesla app covers Powerwall
    "solaredge":       "com.solaredge.homeowner",
    "sense":           "com.sense.androidclient",    # Sense Home
    "span":            "io.span.android.homeowner",  # SPAN Home
    # enphase, emporia, sunpower, generac: not on US Play Store - App Store only
}

MAX_REVIEWS   = 1000   # per app
REVIEWS_BATCH = 200    # google-play-scraper max per request
SLEEP_BETWEEN = 2      # seconds between requests (be polite)

BASE_DIR = Path(__file__).parents[2] / "data"
TEXT_DIR = BASE_DIR / "raw" / "text" / "google_play"
META_DIR = BASE_DIR / "raw" / "metadata" / "google_play"


def fetch_app_info(app_id: str) -> dict:
    info = gp_app(app_id, lang="en", country="us")
    # Keep only serialisable fields
    return {
        "appId":           info.get("appId"),
        "title":           info.get("title"),
        "developer":       info.get("developer"),
        "score":           info.get("score"),
        "ratings":         info.get("ratings"),
        "reviews":         info.get("reviews"),
        "installs":        info.get("installs"),
        "description":     info.get("description"),
        "summary":         info.get("summary"),
        "genre":           info.get("genre"),
        "updated":         info.get("updated"),
        "version":         info.get("version"),
        "scraped_at":      datetime.now(timezone.utc).isoformat(),
    }


def fetch_reviews(app_id: str) -> list[dict]:
    all_reviews = []
    token = None

    while len(all_reviews) < MAX_REVIEWS:
        want = min(REVIEWS_BATCH, MAX_REVIEWS - len(all_reviews))
        result, token = gp_reviews(
            app_id,
            lang="en",
            country="us",
            count=want,
            continuation_token=token,
        )
        if not result:
            break

        for r in result:
            all_reviews.append({
                "reviewId":    r.get("reviewId"),
                "userName":    r.get("userName"),
                "score":       r.get("score"),
                "content":     r.get("content"),
                "thumbsUpCount": r.get("thumbsUpCount"),
                "at":          r["at"].isoformat() if r.get("at") else None,
                "replyContent": r.get("replyContent"),
                "repliedAt":   r["repliedAt"].isoformat() if r.get("repliedAt") else None,
            })

        log.info("  fetched %d reviews so far...", len(all_reviews))

        if token is None:
            break
        time.sleep(SLEEP_BETWEEN)

    return all_reviews


def scrape_app(name: str, app_id: str) -> None:
    log.info("=== Scraping %s (%s) ===", name, app_id)

    text_dir = TEXT_DIR / name
    meta_dir = META_DIR / name
    text_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    # App info
    try:
        info = fetch_app_info(app_id)
        meta_path = meta_dir / "app_info.json"
        meta_path.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("  App info saved → %s (rating: %.1f, installs: %s)",
                 meta_path, info.get("score") or 0, info.get("installs") or "?")
    except NotFoundError:
        log.warning("  App not found on Play Store: %s - skipping", app_id)
        return
    except Exception as exc:
        log.error("  Failed to fetch app info for %s: %s", app_id, exc)
        return

    # Reviews
    try:
        revs = fetch_reviews(app_id)
        reviews_path = text_dir / "reviews.json"
        reviews_path.write_text(
            json.dumps({"app": name, "app_id": app_id, "count": len(revs), "reviews": revs},
                       indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        log.info("  %d reviews saved → %s", len(revs), reviews_path)
    except Exception as exc:
        log.error("  Failed to fetch reviews for %s: %s", app_id, exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Google Play reviews for EV charging apps")
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
        time.sleep(SLEEP_BETWEEN)

    log.info("Done.")


if __name__ == "__main__":
    main()
