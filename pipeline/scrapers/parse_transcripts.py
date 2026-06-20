"""
parse_transcripts.py

Parses a multi-section transcript file into per-app .txt files under
data/raw/text/youtube_summaries/<app_name>/.

Each section in the input file must be separated by a line of 5+ dashes (-----).
The first non-blank, non-URL, non-timestamp line is treated as the title.
App is auto-detected from the title keywords.

Usage:
    python pipeline/scrapers/parse_transcripts.py
    python pipeline/scrapers/parse_transcripts.py --file "C:\\path\\to\\file.txt"
"""

import argparse
import re
import hashlib
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DEFAULT_INPUT = Path(r"C:\Users\Admin\Downloads\AllYoutubeTranscripts.txt")
OUTPUT_BASE   = Path(__file__).parents[2] / "data" / "raw" / "text" / "youtube_summaries"
SCRAPED_AT    = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

# ---------------------------------------------------------------------------
# App-name mapping rules (checked in order against the section title)
# ---------------------------------------------------------------------------
def classify_title(title: str) -> str | None:
    """
    Return app_name string or None (meaning SKIP).
    """
    t = title.lower()

    # Explicit skips
    if "not for apps" in t:
        return None
    if "pod point" in t or "pod-point" in t:
        return None
    # EVCS Tutorial playlist is handled separately (SKIP block)
    if "evcs tutorial" in t and ("playlist" in t or "entier" in t or "entire" in t):
        return None

    # Mappings
    # EV Charging
    if "chargepoint" in t or "charge point" in t or "charge-point" in t:
        return "chargepoint"
    if "evgo" in t or "ev go" in t or "ev-go" in t:
        return "evgo"
    if "electrify america" in t:
        return "electrify_america"
    if "plugshare" in t or "plug share" in t or "plug-share" in t:
        return "plugshare"
    if "shell recharge" in t or "shell-recharge" in t:
        return "shell_recharge"
    if "flo" in t and "enphase" not in t:
        return "flo"
    if "evcs" in t:
        return "evcs"
    if "blink" in t:
        return "blink"
    # Prosumer - check before generic "tesla" to avoid mis-routing
    if "powerwall" in t:
        return "tesla_powerwall"
    if "tesla" in t:
        return "tesla"
    if "enphase" in t or "enlighten" in t:
        return "enphase"
    if "solaredge" in t or "solar edge" in t or "mysolar" in t:
        return "solaredge"
    if "emporia" in t:
        return "emporia"
    if "sense" in t and ("energy" in t or "monitor" in t or "home" in t):
        return "sense"
    if "sunpower" in t or "sun power" in t or "sunstrong" in t:
        return "sunpower"
    if "generac" in t or "pwrview" in t or "pwr view" in t:
        return "generac"
    if "span" in t and ("panel" in t or "smart" in t or "home" in t or "energy" in t):
        return "span"

    return None  # unknown / skip


# ---------------------------------------------------------------------------
# Timestamp / artifact cleaning
# ---------------------------------------------------------------------------
def clean_transcript(text: str) -> str:
    lines = text.splitlines()
    cleaned = []

    for line in lines:
        s = line.strip()

        # Skip empty lines (we'll re-join later)
        if not s:
            cleaned.append("")
            continue

        # Skip pure standalone timestamp lines: "00:00:01", "0:00", "16:34", "1:30:00"
        if re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', s):
            continue

        # Skip "Status: ok" / "Status: no transcript button" lines
        if re.match(r'^Status:', s, re.IGNORECASE):
            continue

        # Skip lines that are just numbered playlist items like "01." / "32."
        if re.match(r'^\d{1,2}\.\s', s) and len(s) < 80:
            # Could be a real sentence - only skip if it looks like a playlist item title
            if re.match(r'^\d{1,2}\.\s+\w[\w\s\-:]+$', s) and len(s) < 60:
                continue

        # Skip chapter headers: "Chapter 1: Intro", "Chapter 1: ..."
        if re.match(r'^Chapter\s+\d+:', s, re.IGNORECASE):
            continue

        # Strip [Music], [Applause], [music], [applause] entirely
        s = re.sub(r'\[Music\]|\[music\]|\[Applause\]|\[applause\]|\[MUSIC\]|\[APPLAUSE\]', '', s).strip()
        if not s:
            continue

        # Remove bracketed timestamps at start: [0:00], [1:23], [12:34:56]
        s = re.sub(r'^\[\d{1,2}:\d{2}(:\d{2})?\]\s*', '', s).strip()
        if not s:
            continue

        # Remove verbose inline "N seconds" / "N minutes" / "N minutes, N seconds" timestamps
        # Patterns like: "0:1515 secondstext", "1:001 minutetext", "2:182 minutes, 18 secondstext"
        # Also: "0:00all right" style (timestamp glued to text)
        # IMPORTANT: put longer alternatives first (seconds before second, minutes before minute)
        # to avoid partial matches that leave a trailing 's'.
        s = re.sub(
            r'^\d{1,2}:\d{2}\s*\d*\s*(?:seconds|second|minutes|minute)(?:,\s*\d+\s*(?:seconds|second))?\s*',
            '', s
        ).strip()

        # Also handle "0:00all right" (no space between timestamp and text), and plain "0:00"
        s = re.sub(r'^\d{1,2}:\d{2}\s*', '', s).strip()

        if not s:
            continue

        # Remove remaining [NN:NN] timestamps anywhere in the line (YouTube sidebar noise)
        # These show up as: [6:44] Ravi Kishan's UNEXPECTED...  → skip whole line if it looks like YT sidebar
        # Heuristic: if line starts with a bracketed timestamp after stripping and the rest looks like
        # a YouTube video title (with view counts / years), skip the whole line
        if re.match(r'^\[\d{1,3}:\d{2}(:\d{2})?\]', s):
            # Check if it looks like YouTube sidebar content (has "views" or "watching" or year pattern)
            if re.search(r'\d+[KMB]?\s+views|watching|\d{1,2}\s+(hours?|days?|weeks?|months?|years?)\s+ago', s):
                continue
            # Otherwise strip the timestamp and keep
            s = re.sub(r'^\[\d{1,3}:\d{2}(:\d{2})?\]\s*', '', s).strip()

        # Remove "N second" / "N minute" style duration prefixes that got left over
        s = re.sub(r'^\d+\s+(?:second|seconds|minute|minutes)(?:,\s*\d+\s*(?:second|seconds))?\s+', '', s).strip()

        if not s:
            continue

        cleaned.append(s)

    # Join lines, collapse multiple blank lines into one
    result = "\n".join(cleaned)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


# ---------------------------------------------------------------------------
# URL / video_id extraction
# ---------------------------------------------------------------------------
YT_URL_RE = re.compile(r'https?://(?:www\.)?youtube\.com/watch\?v=([\w\-]+)')

def extract_video_id(url: str) -> str:
    m = YT_URL_RE.search(url)
    if m:
        return m.group(1)
    return ""

def make_id_from_title(title: str) -> str:
    """Generate a stable hash-based ID when no URL is available."""
    return "hash_" + hashlib.md5(title.encode()).hexdigest()[:10]


# ---------------------------------------------------------------------------
# Section splitting
# ---------------------------------------------------------------------------
DIVIDER_RE = re.compile(r'^-{5,}$')

def split_sections(text: str) -> list[str]:
    """Split the full file by divider lines."""
    sections = []
    current_lines: list[str] = []
    for line in text.splitlines():
        if DIVIDER_RE.match(line.strip()):
            sections.append("\n".join(current_lines))
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append("\n".join(current_lines))
    return sections


# ---------------------------------------------------------------------------
# Parse a single section into (title, url, raw_transcript)
# ---------------------------------------------------------------------------
def is_timestamp_line(s: str) -> bool:
    """Return True if the line looks like a pure timestamp or starts with one."""
    return bool(re.match(r'^\d{1,2}:\d{2}', s) or re.match(r'^\[\d{1,2}:\d{2}', s))


def parse_section(section: str) -> tuple[str, str, str]:
    """
    Returns (title, url, raw_transcript_text).
    Title and URL may be empty strings.

    Header detection rules:
    - URL line: matches YouTube URL regex
    - Title line: a non-empty, non-URL, non-timestamp line that appears BEFORE
      the first timestamp line in the section.
    Once we've seen a timestamp line, we're in transcript content - stop header
    detection.
    """
    lines = section.splitlines()

    # Strip leading blank lines
    while lines and not lines[0].strip():
        lines.pop(0)

    if not lines:
        return ("", "", "")

    title = ""
    url = ""
    content_start = 0

    for idx, raw_line in enumerate(lines):
        s = raw_line.strip()
        if not s:
            continue

        # Once we hit a timestamp, header scanning is over
        if is_timestamp_line(s):
            content_start = idx
            break

        if YT_URL_RE.match(s):
            if not url:
                url = s
                content_start = idx + 1
        elif not title:
            title = s
            content_start = idx + 1
    else:
        # No timestamp found - all content is header or empty
        pass

    # Collect the transcript (everything from content_start onward)
    transcript_lines = lines[content_start:]
    raw_transcript = "\n".join(transcript_lines)

    return (title, url, raw_transcript)


# ---------------------------------------------------------------------------
# Save helpers  - writes one .txt per video to youtube_summaries/<app>/
# ---------------------------------------------------------------------------
def existing_video_ids(app_name: str) -> set[str]:
    """Return video_ids already saved as .txt files for this app."""
    folder = OUTPUT_BASE / app_name
    if not folder.exists():
        return set()
    ids = set()
    for f in folder.glob("*.txt"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("Video ID:"):
                ids.add(line.split(":", 1)[1].strip())
                break
    return ids


def save_video_txt(app_name: str, video_id: str, title: str, url: str, body: str) -> Path:
    """Write one .txt summary file in the format read_youtube() expects."""
    folder = OUTPUT_BASE / app_name
    folder.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r'[^\w\-]', '_', video_id)[:40]
    path = folder / f"{safe_id}.txt"
    content = (
        f"Title:    {title}\n"
        f"Video ID: {video_id}\n"
        f"URL:      {url or ''}\n"
        f"App:      {app_name}\n"
        f"\n"
        f"{body}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Parse multi-section transcript file into per-app .txt files")
    parser.add_argument("--file", type=Path, default=DEFAULT_INPUT,
                        help="Path to the input transcript file (default: %(default)s)")
    args = parser.parse_args()

    input_file: Path = args.file
    if not input_file.exists():
        print(f"ERROR: Input file not found: {input_file}")
        return

    raw = input_file.read_text(encoding="utf-8")
    sections = split_sections(raw)

    saved:   dict[str, int] = {}  # app_name -> count saved this run
    skipped: list[str] = []

    # Pre-load existing video IDs per app to deduplicate
    seen_ids: dict[str, set] = {}

    in_evcs_playlist = False

    for section in sections:
        section = section.strip()
        if not section:
            continue

        title, url, raw_transcript = parse_section(section)

        # EVCS playlist block detection
        if "evcs tutorial" in title.lower() and ("playlist" in title.lower() or "entier" in title.lower() or "entire" in title.lower()):
            in_evcs_playlist = True
            skipped.append(f"{title} (European hardware brand EVCS, entire playlist)")
            continue

        if in_evcs_playlist:
            test_app = classify_title(title) if title else None
            if title and (test_app is not None or "pod point" in title.lower()):
                in_evcs_playlist = False
            else:
                continue

        # Classify
        if not title and not url:
            app_name = "shell_recharge"
            title = "(Shell Recharge - add payment method)"
        elif not title and url:
            skipped.append(f"(no title, url={url})")
            continue
        else:
            app_name = classify_title(title)

        if app_name is None:
            tl = title.lower()
            if "not for apps" in tl:        reason = "not an app review"
            elif "pod point" in tl:          reason = "UK brand"
            elif "evcs tutorial" in tl:      reason = "European hardware brand"
            else:                            reason = "no matching app"
            skipped.append(f"{title or '(no title)'} ({reason})")
            continue

        # Clean
        cleaned = clean_transcript(raw_transcript)
        if len(cleaned.strip()) < 50:
            skipped.append(f"{title} (too little content after cleaning)")
            continue

        # Deduplicate
        video_id = extract_video_id(url) if url else ""
        if not video_id:
            video_id = make_id_from_title(title)

        if app_name not in seen_ids:
            seen_ids[app_name] = existing_video_ids(app_name)

        if video_id in seen_ids[app_name]:
            print(f"  [skip duplicate] {title} (video_id={video_id})")
            continue

        # Save
        path = save_video_txt(app_name, video_id, title, url, cleaned)
        seen_ids[app_name].add(video_id)
        saved[app_name] = saved.get(app_name, 0) + 1
        print(f"  [saved] {app_name} - {title[:60]} -> {path.name}")

    # Summary
    print("\n=== SUMMARY ===")
    for app_name in sorted(saved.keys()):
        print(f"  {app_name}: {saved[app_name]} new file(s)")
    if not saved:
        print("  (nothing new saved)")
    print(f"\nSkipped: {len(skipped)}")
    for s in skipped:
        print(f"  SKIP: {s}")

    if saved:
        print("\nNext step - ingest into DB:")
        for app_name in sorted(saved.keys()):
            print(f"  python pipeline/run_pipeline.py --source youtube --app {app_name}")


if __name__ == "__main__":
    main()
