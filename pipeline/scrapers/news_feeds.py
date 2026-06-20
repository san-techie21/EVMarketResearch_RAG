"""
News ingestion v3 — free, full-text, multi-source, relevance-matched.

Why this exists
---------------
The original `news_rss.py` pulled Google News *search* RSS. Google News `<link>`s
are encoded redirect URLs (`news.google.com/rss/articles/CBMi...`), so
`trafilatura.fetch_url(link)` hits a redirect/consent page and returns nothing —
which is why most stored "news" chunks were headline-only. (Verified empirically.)

This scraper instead pulls **publisher-direct RSS feeds** whose `<link>`s are real
article URLs, so full-body extraction actually works. Every feed below was
validated end-to-end (reachable, parsed, fresh, body-extractable) before being
included — see the project's feed-test harness.

Sources (all free, no paid API key)
  1. Publisher RSS feeds — full text via `content:encoded` when present, else
     fetched from the real article URL with trafilatura (browser-UA requests
     fallback for publishers that block bot fetches, e.g. InsideEVs).
  2. GDELT 2.0 DOC API — keyless, broad coverage; best-effort (rate-limited).
  3. Google News RSS — OPTIONAL supplement (--google-news); links are encoded so
     bodies are summary-only unless a decoder succeeds.

Each article is keyword-matched to one or more target apps, tagged with category,
given a real `published_at` UTC timestamp, and deduped by canonical URL + title.

Usage
    python pipeline/scrapers/news_feeds.py
    python pipeline/scrapers/news_feeds.py --no-body          # fast, feed text only
    python pipeline/scrapers/news_feeds.py --app chargepoint enphase
    python pipeline/scrapers/news_feeds.py --gdelt            # also query GDELT
    python pipeline/scrapers/news_feeds.py --max-per-feed 40

Output (back-compatible with pipeline/run_pipeline.py::read_news)
    data/raw/text/news/<app_name>/articles.json
"""
from __future__ import annotations

import argparse
import html
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

import requests
import feedparser
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    import trafilatura
    _HAVE_TRAFILATURA = True
except ImportError:
    _HAVE_TRAFILATURA = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validated publisher feeds  (name, url, category_hint)
#   category_hint ∈ {"ev", "energy", "mixed"} — only used to disambiguate the
#   _general bucket; app keyword matches always take precedence.
# ---------------------------------------------------------------------------
PUBLISHER_FEEDS: list[tuple[str, str, str]] = [
    # EV / charging
    ("Electrek",            "https://electrek.co/feed/",                                              "mixed"),
    ("InsideEVs",           "https://insideevs.com/rss/articles/all/",                                "ev"),
    ("Teslarati",           "https://www.teslarati.com/feed/",                                        "ev"),
    ("TheDriven",           "https://thedriven.io/feed/",                                             "ev"),
    ("ChargedEVs",          "https://chargedevs.com/feed/",                                           "ev"),
    ("CnEVPost",            "https://cnevpost.com/feed/",                                             "ev"),
    ("Electrive",           "https://www.electrive.com/feed/",                                        "ev"),
    ("CleanTechnica",       "https://cleantechnica.com/feed/",                                        "mixed"),
    ("EVCentral",           "https://evcentral.com.au/feed/",                                         "ev"),
    # Energy / solar / storage / prosumer
    ("PVMagazineUSA",       "https://pv-magazine-usa.com/feed/",                                      "energy"),
    ("PVMagazineGlobal",    "https://www.pv-magazine.com/feed/",                                      "energy"),
    ("SolarPowerWorld",     "https://www.solarpowerworldonline.com/feed/",                            "energy"),
    ("SolarBuilder",        "https://solarbuildermag.com/feed/",                                      "energy"),
    ("EnergyStorageNews",   "https://www.energy-storage.news/feed/",                                  "energy"),
    ("ESSNews",             "https://www.ess-news.com/feed/",                                         "energy"),
    ("PVTech",              "https://www.pv-tech.org/feed/",                                          "energy"),
    ("CanaryMedia",         "https://www.canarymedia.com/articles/rss",                               "energy"),
]

# ---------------------------------------------------------------------------
# App relevance matching.  Aliases are lowercase substrings; ambiguous short
# names (blink, flo, sense, span, tesla) use phrase forms to avoid false hits.
# ---------------------------------------------------------------------------
APP_ALIASES: dict[str, list[str]] = {
    # EV charging
    "chargepoint":       ["chargepoint"],
    "evgo":              ["evgo", "ev go "],
    "blink":             ["blink charging", "blink charger", "blink network", "blink ev"],
    "plugshare":         ["plugshare"],
    "electrify_america": ["electrify america", "electrify canada"],
    "flo":               ["flo ev", "flo charging", "flo charger", "flo network", "addenergie", "addénergie"],
    "evcs":              ["evcs"],
    "shell_recharge":    ["shell recharge", "shellrecharge", "greenlots"],
    "tesla":             ["supercharger", "superchargers", "tesla charging",
                          "tesla charger", "tesla app", "nacs", "tesla powershare"],
    # Prosumer / home energy
    "tesla_powerwall":   ["powerwall"],
    "enphase":           ["enphase"],
    "solaredge":         ["solaredge", "solar edge"],
    "emporia":           ["emporia"],
    "sense":             ["sense energy", "sense home energy", "sense monitor", "sense.com"],
    "sunpower":          ["sunpower", "sun power"],
    "generac":           ["generac", "pwrcell", "pwrview"],
    "span":              ["span.io", "span smart panel", "span panel", "span drive"],
}

APP_CATEGORIES: dict[str, str] = {
    "chargepoint": "ev_charging", "evgo": "ev_charging", "blink": "ev_charging",
    "plugshare": "ev_charging", "electrify_america": "ev_charging", "flo": "ev_charging",
    "evcs": "ev_charging", "shell_recharge": "ev_charging", "tesla": "ev_charging",
    "tesla_powerwall": "prosumer", "enphase": "prosumer", "solaredge": "prosumer",
    "emporia": "prosumer", "sense": "prosumer", "sunpower": "prosumer",
    "generac": "prosumer", "span": "prosumer",
}

# General-interest keywords → assign to _general bucket when no specific app matches.
EV_GENERAL_KEYWORDS = [
    "ev charging", "electric vehicle charging", "charging network", "charging station",
    "fast charging", "dc fast charg", "public charging", "charging infrastructure",
    "nacs", "ccs charg", "ev charger", "charging app",
]
ENERGY_GENERAL_KEYWORDS = [
    "home solar", "rooftop solar", "residential solar", "home battery",
    "home energy", "energy storage", "virtual power plant", "solar monitoring",
    "battery storage", "home energy management", "solar battery",
]

# ---------------------------------------------------------------------------
# HTTP / config
# ---------------------------------------------------------------------------
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, text/html, */*"})

FEED_TIMEOUT   = 20
BODY_TIMEOUT   = 15
BODY_SLEEP     = 0.4
FEED_SLEEP     = 0.3
MIN_BODY_CHARS = 500     # below this we try the next extraction tier
BASE_DIR       = Path(__file__).parents[2] / "data"
TEXT_DIR       = BASE_DIR / "raw" / "text" / "news"

GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_QUERIES  = ['"EV charging"', '"home battery"', '"rooftop solar" app']


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------
_TAG_RE   = re.compile(r"<[^>]+>")
_WS_RE    = re.compile(r"[ \t]+")
_NL_RE    = re.compile(r"\n{3,}")


def html_to_text(s: str) -> str:
    """Strip tags + unescape entities from an HTML fragment (content:encoded)."""
    if not s:
        return ""
    s = _TAG_RE.sub(" ", s)
    s = html.unescape(s)
    s = _WS_RE.sub(" ", s)
    s = _NL_RE.sub("\n\n", s)
    return s.strip()


def canonicalize_url(url: str) -> str:
    """Lowercase host, drop query/fragment, strip trailing slash."""
    if not url:
        return ""
    try:
        p = urlparse(url)
        netloc = p.netloc.lower()
        path = p.path.rstrip("/")
        return urlunparse((p.scheme or "https", netloc, path, "", "", ""))
    except Exception:
        return url


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").lower()).strip()


def parse_published(entry) -> tuple[str, str | None]:
    """Return (human_string, iso_utc_or_None) from a feedparser entry."""
    human = (entry.get("published") or entry.get("updated") or "").strip()
    st = entry.get("published_parsed") or entry.get("updated_parsed")
    iso = None
    if st:
        try:
            iso = datetime(*st[:6], tzinfo=timezone.utc).isoformat()
        except Exception:
            iso = None
    return human, iso


# ---------------------------------------------------------------------------
# Body extraction — 3-tier with graceful fallback
# ---------------------------------------------------------------------------
def _extract_from_html(downloaded: str) -> str:
    if not downloaded:
        return ""
    text = trafilatura.extract(
        downloaded, include_comments=False, include_tables=True,
        no_fallback=False, favor_recall=True,
    )
    return (text or "").strip()


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _browser_fetch(url: str) -> str:
    resp = SESSION.get(url, timeout=BODY_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def fetch_full_body(url: str) -> tuple[str, str]:
    """Return (body, method). Tries trafilatura.fetch_url, then browser-UA requests."""
    if not _HAVE_TRAFILATURA or not url:
        return "", "none"
    # Tier A: trafilatura's own fetcher
    try:
        downloaded = trafilatura.fetch_url(url, timeout=BODY_TIMEOUT)
        body = _extract_from_html(downloaded) if downloaded else ""
        if len(body) >= MIN_BODY_CHARS:
            return body, "trafilatura"
    except Exception as exc:
        log.debug("trafilatura.fetch_url failed for %s: %s", url, exc)
    # Tier B: browser-UA requests (handles publishers that block bot fetchers)
    try:
        html_txt = _browser_fetch(url)
        body = _extract_from_html(html_txt)
        if len(body) >= MIN_BODY_CHARS:
            return body, "requests"
        if body:
            return body, "requests-thin"
    except Exception as exc:
        log.debug("browser fetch failed for %s: %s", url, exc)
    return "", "failed"


def entry_body(entry, fetch_body: bool) -> tuple[str, str, str]:
    """
    Resolve (description, body, body_source) for a feed entry.
      - description: always the short summary text.
      - body: best full text available.
      - body_source: where the body came from.
    """
    summary = html_to_text(entry.get("summary", ""))

    # content:encoded (feedparser -> entry.content[i].value)
    ce = ""
    if entry.get("content"):
        ce = max((c.get("value", "") for c in entry["content"]), key=len, default="")
    ce_text = html_to_text(ce)
    if len(ce_text) >= MIN_BODY_CHARS:
        return summary, ce_text, "content_encoded"

    # Fetch the real article URL
    if fetch_body:
        body, method = fetch_full_body(entry.get("link", ""))
        if len(body) >= MIN_BODY_CHARS:
            return summary, body, method

    # Fall back to the richest short text we have
    best = ce_text if len(ce_text) > len(summary) else summary
    return summary, best, "summary"


# ---------------------------------------------------------------------------
# Relevance matching
#
# Word-boundary regex (not naive substring) so brand names don't match generic
# industry terms — e.g. "chargepoint" must NOT match the generic plural
# "chargepoints" (as in "Char.gy delivers 1000 new chargepoints"). Verified
# against a real false positive during end-to-end testing.
# ---------------------------------------------------------------------------
_APP_PATTERNS: dict[str, list[re.Pattern]] = {
    app: [re.compile(r"\b" + re.escape(alias.strip()) + r"\b", re.IGNORECASE)
          for alias in aliases]
    for app, aliases in APP_ALIASES.items()
}


def match_apps(text: str) -> list[str]:
    matched = []
    for app, patterns in _APP_PATTERNS.items():
        if any(p.search(text) for p in patterns):
            matched.append(app)
    return matched


def general_category(text: str, feed_hint: str) -> str | None:
    t = text.lower()
    ev = any(k in t for k in EV_GENERAL_KEYWORDS)
    en = any(k in t for k in ENERGY_GENERAL_KEYWORDS)
    if ev and not en:
        return "ev_charging"
    if en and not ev:
        return "prosumer"
    if ev and en:
        return "ev_charging" if feed_hint != "energy" else "prosumer"
    if feed_hint == "ev":
        return "ev_charging"
    if feed_hint == "energy":
        return "prosumer"
    return None


# ---------------------------------------------------------------------------
# Feed scraping
# ---------------------------------------------------------------------------
def fetch_feed(url: str):
    resp = SESSION.get(url, timeout=FEED_TIMEOUT)
    resp.raise_for_status()
    return feedparser.parse(resp.content)


def collect_publisher_articles(fetch_body: bool, max_per_feed: int,
                               app_filter: set[str] | None) -> dict[str, list[dict]]:
    """Return {app_or_general: [article, ...]} from all publisher feeds."""
    buckets: dict[str, list[dict]] = {}
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()

    for name, url, hint in PUBLISHER_FEEDS:
        log.info("=== Feed: %s ===", name)
        try:
            parsed = fetch_feed(url)
        except Exception as exc:
            log.warning("  feed fetch failed (%s): %s", name, exc)
            continue

        entries = (parsed.entries or [])[:max_per_feed]
        kept = 0
        for entry in entries:
            title = (entry.get("title") or "").strip()
            link  = canonicalize_url(entry.get("link", ""))
            if not title or not link:
                continue
            ntitle = normalize_title(title)
            if link in seen_urls or ntitle in seen_titles:
                continue

            # Match on title + summary first (cheap), before any body fetch
            summary_preview = html_to_text(entry.get("summary", ""))
            match_text = f"{title} {summary_preview}"
            apps = match_apps(match_text)

            targets: list[tuple[str, str]] = []  # (bucket, category)
            if apps:
                if app_filter:
                    apps = [a for a in apps if a in app_filter]
                    if not apps:
                        continue
                for a in apps:
                    targets.append((a, APP_CATEGORIES.get(a, "ev_charging")))
            else:
                if app_filter:
                    continue  # only want specific apps
                cat = general_category(match_text, hint)
                if cat is None:
                    continue
                targets.append(("_general", cat))

            # Now resolve the body (once) and attach to each target bucket
            description, body, body_source = entry_body(entry, fetch_body)
            human_date, iso_date = parse_published(entry)
            if fetch_body and body_source in ("trafilatura", "requests", "requests-thin"):
                time.sleep(BODY_SLEEP)

            seen_urls.add(link)
            seen_titles.add(ntitle)
            kept += 1

            for bucket, category in targets:
                article = {
                    "title":       title,
                    "link":        link,
                    "description": description,
                    "body":        body,
                    "source":      name,            # back-compat: 'source' = publisher
                    "publisher":   name,
                    "published":   human_date,
                    "published_at": iso_date,
                    "category":    category,
                    "matched_app": bucket,
                    "body_source": body_source,
                    "query":       name,            # back-compat
                    "fetched_at":  datetime.now(timezone.utc).isoformat(),
                }
                buckets.setdefault(bucket, []).append(article)

        log.info("  %s: kept %d/%d entries", name, kept, len(entries))
        time.sleep(FEED_SLEEP)

    return buckets


def collect_gdelt_articles(app_filter: set[str] | None) -> dict[str, list[dict]]:
    """Best-effort GDELT 2.0 DOC API (keyless). Returns same bucket shape."""
    buckets: dict[str, list[dict]] = {}
    for query in GDELT_QUERIES:
        params = f"?query={quote(query)}&mode=ArtList&maxrecords=40&format=json&timespan=7d&sort=datedesc"
        ok = False
        for attempt in range(3):
            try:
                r = SESSION.get(GDELT_ENDPOINT + params, timeout=25)
                if r.status_code == 429:
                    time.sleep(5 * (attempt + 1))
                    continue
                r.raise_for_status()
                data = r.json()
                ok = True
                break
            except Exception as exc:
                log.debug("GDELT '%s' attempt %d failed: %s", query, attempt + 1, exc)
                time.sleep(3)
        if not ok:
            log.warning("  GDELT query failed: %s", query)
            continue

        for a in data.get("articles", []):
            title = (a.get("title") or "").strip()
            link  = canonicalize_url(a.get("url", ""))
            if not title or not link:
                continue
            match_text = title
            apps = match_apps(match_text)
            targets: list[tuple[str, str]] = []
            if apps:
                if app_filter:
                    apps = [x for x in apps if x in app_filter]
                    if not apps:
                        continue
                for x in apps:
                    targets.append((x, APP_CATEGORIES.get(x, "ev_charging")))
            else:
                if app_filter:
                    continue
                cat = general_category(match_text, "mixed")
                if cat is None:
                    continue
                targets.append(("_general", cat))

            seendate = a.get("seendate", "")
            iso = None
            try:  # GDELT format: 20260618T093000Z
                iso = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
            except Exception:
                pass

            for bucket, category in targets:
                buckets.setdefault(bucket, []).append({
                    "title":       title,
                    "link":        link,
                    "description": "",
                    "body":        "",
                    "source":      a.get("domain", "GDELT"),
                    "publisher":   a.get("domain", "GDELT"),
                    "published":   seendate,
                    "published_at": iso,
                    "category":    category,
                    "matched_app": bucket,
                    "body_source": "gdelt-title",
                    "query":       "gdelt",
                    "fetched_at":  datetime.now(timezone.utc).isoformat(),
                })
        time.sleep(1.0)
    return buckets


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def write_bucket(app_name: str, articles: list[dict]) -> None:
    out_dir = TEXT_DIR / app_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # Merge with any existing articles, dedup by canonical link
    existing: list[dict] = []
    out_path = out_dir / "articles.json"
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8")).get("articles", [])
        except Exception:
            existing = []

    by_link: dict[str, dict] = {}
    for a in existing + articles:
        link = canonicalize_url(a.get("link", ""))
        if not link:
            continue
        # Prefer the version with a longer body
        if link not in by_link or len(a.get("body", "")) > len(by_link[link].get("body", "")):
            by_link[link] = a

    merged = sorted(
        by_link.values(),
        key=lambda a: a.get("published_at") or "",
        reverse=True,
    )
    body_count = sum(1 for a in merged if len(a.get("body", "")) >= MIN_BODY_CHARS)

    out_path.write_text(
        json.dumps({
            "app":        app_name,
            "count":      len(merged),
            "body_count": body_count,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "articles":   merged,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("  %-20s %3d articles (%d full-body) -> %s",
             app_name, len(merged), body_count, out_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="v3 full-text news scraper (publisher RSS + GDELT)")
    parser.add_argument("--app", nargs="+", choices=list(APP_ALIASES.keys()),
                        help="Only collect articles matching these apps (default: all + general)")
    parser.add_argument("--no-body", action="store_true",
                        help="Skip full-body fetch (use feed text only — fast)")
    parser.add_argument("--gdelt", action="store_true",
                        help="Also query the GDELT API (keyless, best-effort)")
    parser.add_argument("--max-per-feed", type=int, default=60,
                        help="Max entries to consider per feed (default 60)")
    args = parser.parse_args()

    fetch_body = not args.no_body
    if fetch_body and not _HAVE_TRAFILATURA:
        log.warning("trafilatura not installed — falling back to feed text only. "
                    "Install with: pip install trafilatura")
        fetch_body = False

    app_filter = set(args.app) if args.app else None

    log.info("Full-body extraction: %s | GDELT: %s | apps: %s",
             "ON" if fetch_body else "OFF", "ON" if args.gdelt else "OFF",
             ", ".join(sorted(app_filter)) if app_filter else "ALL")

    buckets = collect_publisher_articles(fetch_body, args.max_per_feed, app_filter)

    if args.gdelt:
        log.info("=== GDELT ===")
        gdelt_buckets = collect_gdelt_articles(app_filter)
        for k, v in gdelt_buckets.items():
            buckets.setdefault(k, []).extend(v)

    if not buckets:
        log.warning("No matching articles found.")
        return

    log.info("=== Writing %d buckets ===", len(buckets))
    total = 0
    for app_name, articles in sorted(buckets.items()):
        write_bucket(app_name, articles)
        total += len(articles)
    log.info("Done. %d articles across %d buckets.", total, len(buckets))


if __name__ == "__main__":
    main()
