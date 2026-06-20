"""
Reddit scraper using public JSON endpoints - no API key required.
Searches r/electricvehicles and r/ChargingStations for each target app.

Usage:
    python pipeline/scrapers/reddit.py
    python pipeline/scrapers/reddit.py --app chargepoint evgo

Output:
    data/raw/text/reddit/<app_name>/posts.json
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
# Config
# ---------------------------------------------------------------------------
SUBREDDITS = ["electricvehicles", "ChargingStations", "teslamotors", "evs"]

APP_QUERIES = {
    "chargepoint":       ["ChargePoint", "ChargePoint app", "ChargePoint charging"],
    "evgo":              ["EVgo", "EVgo charger", "EVgo app"],
    "blink":             ["Blink charging", "Blink charger", "Blink EV"],
    "plugshare":         ["PlugShare", "PlugShare app"],
    "electrify_america": ["Electrify America", "EA charging"],
    "flo":               ["FLO EV", "FLO charging"],
    "evcs":              ["EVCS charging"],
    "shell_recharge":    ["Shell Recharge", "Greenlots"],
    "tesla":             ["Tesla app", "Tesla charging", "Tesla supercharger"],
}

MAX_POSTS_PER_QUERY = 25     # Reddit returns max 100 per request; 25 keeps it polite
SLEEP_SECS          = 2

BASE_DIR = Path(__file__).parents[2] / "data"
TEXT_DIR = BASE_DIR / "raw" / "text" / "reddit"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "ev-research-scraper/1.0 (research only; read-only)",
})


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _get_json(url: str, params: dict = None) -> dict:
    resp = SESSION.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_subreddit_search(subreddit: str, query: str, limit: int = 25) -> list[dict]:
    """Search a subreddit for posts matching query."""
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q":          query,
        "restrict_sr": "true",
        "sort":       "relevance",
        "t":          "all",
        "limit":      min(limit, 100),
    }
    data = _get_json(url, params)
    posts = []
    for child in data.get("data", {}).get("children", []):
        p = child.get("data", {})
        if not p.get("selftext") and not p.get("title"):
            continue
        posts.append({
            "post_id":    p.get("id"),
            "title":      p.get("title", ""),
            "selftext":   p.get("selftext", ""),
            "score":      p.get("score"),
            "url":        p.get("url"),
            "permalink":  f"https://reddit.com{p.get('permalink', '')}",
            "subreddit":  p.get("subreddit"),
            "author":     p.get("author"),
            "num_comments": p.get("num_comments"),
            "created_utc": datetime.fromtimestamp(
                p.get("created_utc", 0), tz=timezone.utc
            ).isoformat(),
            "upvote_ratio": p.get("upvote_ratio"),
        })
    return posts


def fetch_top_posts(subreddit: str, limit: int = 25) -> list[dict]:
    """Fetch top posts from a subreddit (general EV discussion)."""
    url = f"https://www.reddit.com/r/{subreddit}/top.json"
    params = {"t": "year", "limit": min(limit, 100)}
    data = _get_json(url, params)
    posts = []
    for child in data.get("data", {}).get("children", []):
        p = child.get("data", {})
        posts.append({
            "post_id":    p.get("id"),
            "title":      p.get("title", ""),
            "selftext":   p.get("selftext", ""),
            "score":      p.get("score"),
            "url":        p.get("url"),
            "permalink":  f"https://reddit.com{p.get('permalink', '')}",
            "subreddit":  p.get("subreddit"),
            "author":     p.get("author"),
            "num_comments": p.get("num_comments"),
            "created_utc": datetime.fromtimestamp(
                p.get("created_utc", 0), tz=timezone.utc
            ).isoformat(),
            "upvote_ratio": p.get("upvote_ratio"),
        })
    return posts


def scrape_app(name: str, queries: list[str]) -> None:
    log.info("=== Scraping Reddit for: %s ===", name)
    out_dir = TEXT_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)

    seen_ids = set()
    all_posts = []

    for subreddit in SUBREDDITS:
        for query in queries:
            try:
                posts = fetch_subreddit_search(subreddit, query, MAX_POSTS_PER_QUERY)
                new = [p for p in posts if p["post_id"] not in seen_ids]
                seen_ids.update(p["post_id"] for p in new)
                all_posts.extend(new)
                log.info("  r/%s | '%s' -> %d new posts (total: %d)",
                         subreddit, query, len(new), len(all_posts))
            except Exception as exc:
                log.warning("  r/%s | '%s' failed: %s", subreddit, query, exc)
            time.sleep(SLEEP_SECS)

    out_path = out_dir / "posts.json"
    out_path.write_text(
        json.dumps({"app": name, "count": len(all_posts), "posts": all_posts},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("  Saved %d posts -> %s", len(all_posts), out_path)


def scrape_general() -> None:
    """Scrape top posts from EV subreddits for general context."""
    log.info("=== Scraping general EV subreddit posts ===")
    out_dir = TEXT_DIR / "_general"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_posts = []
    seen_ids = set()
    for subreddit in SUBREDDITS:
        try:
            posts = fetch_top_posts(subreddit, limit=50)
            new = [p for p in posts if p["post_id"] not in seen_ids]
            seen_ids.update(p["post_id"] for p in new)
            all_posts.extend(new)
            log.info("  r/%s top posts: %d", subreddit, len(new))
        except Exception as exc:
            log.warning("  r/%s failed: %s", subreddit, exc)
        time.sleep(SLEEP_SECS)

    out_path = out_dir / "posts.json"
    out_path.write_text(
        json.dumps({"app": "_general", "count": len(all_posts), "posts": all_posts},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("  Saved %d general posts", len(all_posts))


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Reddit EV discussions")
    parser.add_argument("--app", nargs="+", choices=list(APP_QUERIES.keys()),
                        help="Scrape specific apps only (default: all)")
    args = parser.parse_args()

    targets = {k: v for k, v in APP_QUERIES.items()
               if not args.app or k in args.app}

    # General subreddit posts first
    scrape_general()

    for name, queries in targets.items():
        try:
            scrape_app(name, queries)
        except Exception as exc:
            log.error("Unexpected error scraping %s: %s", name, exc)

    log.info("Done.")


if __name__ == "__main__":
    main()
