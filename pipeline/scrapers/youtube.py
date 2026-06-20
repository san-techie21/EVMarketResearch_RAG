"""
YouTube scraper - searches for EV charging app videos via YouTube Data API v3
and fetches transcripts using yt-dlp (bypasses IP-based blocking).

Usage:
    python pipeline/scrapers/youtube.py
    python pipeline/scrapers/youtube.py --app chargepoint evgo

Output:
    data/raw/text/youtube/<app_name>/transcripts.json
"""
import argparse
import json
import logging
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yt_dlp
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / "config" / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]

SEARCH_QUERIES = {
    "chargepoint":       "ChargePoint EV charging app review demo tutorial",
    "evgo":              "EVgo fast charging app review demo tutorial",
    "blink":             "Blink Charging EV app review demo tutorial",
    "plugshare":         "PlugShare EV charging app review demo tutorial",
    "electrify_america": "Electrify America charging app review demo tutorial",
    "flo":               "FLO EV charging app review demo tutorial",
    "evcs":              "EVCS electric vehicle charging app review tutorial",
    "shell_recharge":    "Shell Recharge EV charging app review tutorial",
    "tesla":             "Tesla app EV charging review demo tutorial",
}

MAX_RESULTS = 20
SLEEP_SECS  = 0.5
BASE_DIR    = Path(__file__).parents[2] / "data"
TEXT_DIR    = BASE_DIR / "raw" / "text" / "youtube"

SESSION = requests.Session()

_VTT_JUNK = re.compile(
    r"WEBVTT[^\n]*\n|Kind:[^\n]*\n|Language:[^\n]*\n|"
    r"\d{2}:\d{2}:\d{2}\.\d{3} --> [^\n]*\n|"
    r"<[^>]+>|align:[^\n]*\n",
    re.MULTILINE,
)


def _vtt_to_text(vtt: str) -> str:
    """Strip VTT headers, timestamps, and inline tags; collapse duplicate tokens."""
    text = _VTT_JUNK.sub(" ", vtt)
    tokens, seen = [], set()
    for tok in text.split():
        if tok not in seen:
            tokens.append(tok)
            seen.add(tok)
    return " ".join(tokens).strip()


def fetch_transcript(video_id: str) -> str | None:
    """Download subtitle via yt-dlp (handles impersonation headers) and strip to plain text."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmpdir:
        outtmpl = str(Path(tmpdir) / "sub")
        opts = {
            "skip_download":     True,
            "writesubtitles":    True,
            "writeautomaticsub": True,
            "subtitleslangs":    ["en"],
            "subtitlesformat":   "vtt",
            "outtmpl":           outtmpl,
            "quiet":             True,
            "no_warnings":       True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            sub_files = list(Path(tmpdir).glob("*.vtt"))
            if not sub_files:
                return None
            return _vtt_to_text(sub_files[0].read_text(encoding="utf-8")) or None
        except Exception as exc:
            log.debug("Transcript fetch failed for %s: %s", video_id, exc)
            return None


def search_videos(query: str) -> list[dict]:
    resp = SESSION.get(
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "part":                "snippet",
            "q":                   query,
            "type":                "video",
            "maxResults":          MAX_RESULTS,
            "relevanceLanguage":   "en",
            "regionCode":          "US",
            "videoCaptionFilter":  "closedCaption",
            "key":                 YOUTUBE_API_KEY,
        },
        timeout=15,
    )
    resp.raise_for_status()
    videos = []
    for item in resp.json().get("items", []):
        video_id = item["id"].get("videoId")
        if not video_id:
            continue
        snippet = item.get("snippet", {})
        videos.append({
            "video_id":     video_id,
            "title":        snippet.get("title", ""),
            "channel":      snippet.get("channelTitle", ""),
            "published_at": snippet.get("publishedAt", ""),
            "description":  snippet.get("description", ""),
        })
    return videos


def scrape_app(name: str, query: str) -> None:
    log.info("=== Scraping YouTube for: %s ===", name)
    out_dir = TEXT_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)

    videos = search_videos(query)
    log.info("  Found %d videos", len(videos))

    results = []
    for video in videos:
        transcript = fetch_transcript(video["video_id"])
        if transcript:
            video["transcript"] = transcript
            video["transcript_chars"] = len(transcript)
            results.append(video)
            log.info("  [OK] %s - %d chars", video["title"][:60], len(transcript))
        else:
            log.info("  [NO TRANSCRIPT] %s", video["title"][:60])
        time.sleep(SLEEP_SECS)

    out_path = out_dir / "transcripts.json"
    out_path.write_text(
        json.dumps({
            "app":        name,
            "query":      query,
            "count":      len(results),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "transcripts": results,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("  Saved %d transcripts -> %s", len(results), out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape YouTube transcripts for EV charging apps")
    parser.add_argument("--app", nargs="+", choices=list(SEARCH_QUERIES.keys()),
                        help="Scrape specific apps only (default: all)")
    args = parser.parse_args()

    targets = {k: v for k, v in SEARCH_QUERIES.items()
               if not args.app or k in args.app}

    for name, query in targets.items():
        try:
            scrape_app(name, query)
        except Exception as exc:
            log.error("Unexpected error scraping %s: %s", name, exc)

    log.info("Done.")


if __name__ == "__main__":
    main()
