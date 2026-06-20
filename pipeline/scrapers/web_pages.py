"""
Web pages scraper using Firecrawl - scrapes official EV charging app websites,
feature pages, and pricing pages for each target app.

Usage:
    python pipeline/scrapers/web_pages.py
    python pipeline/scrapers/web_pages.py --app chargepoint evgo

Output:
    data/raw/text/web_pages/<app_name>/pages.json

Free tier: 500 credits (one per page). Total target: ~27 pages.
"""
import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from firecrawl import FirecrawlApp

load_dotenv(Path(__file__).parents[2] / "config" / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

APP_URLS: dict[str, list[str]] = {
    "chargepoint": [
        "https://www.chargepoint.com/drivers/",
        "https://www.chargepoint.com/drivers/app/",
        "https://www.chargepoint.com/business/pricing/",
    ],
    "evgo": [
        "https://www.evgo.com/",
        "https://www.evgo.com/evgo-app/",
        "https://www.evgo.com/plans/",
    ],
    "blink": [
        "https://www.blinkcharging.com/drivers/",
        "https://www.blinkcharging.com/products/ev-charging-app/",
        "https://www.blinkcharging.com/pricing/",
    ],
    "plugshare": [
        "https://www.plugshare.com/",
        "https://www.plugshare.com/about.html",
    ],
    "electrify_america": [
        "https://www.electrifyamerica.com/",
        "https://www.electrifyamerica.com/mobile-app/",
        "https://www.electrifyamerica.com/pricing/",
    ],
    "flo": [
        "https://flo.com/en_us/",
        "https://flo.com/en_us/charging-for-drivers/",
        "https://flo.com/en_us/plans-and-pricing/",
    ],
    "evcs": [
        "https://evcs.com/",
        "https://evcs.com/drivers/",
        "https://evcs.com/pricing/",
    ],
    "shell_recharge": [
        "https://shellrecharge.com/en-us/",
        "https://shellrecharge.com/en-us/solutions/drivers",
    ],
    "tesla": [
        "https://www.tesla.com/supercharger",
        "https://www.tesla.com/support/charging",
        "https://www.tesla.com/support/car-apps",
    ],
    # Prosumer / Home Energy
    "tesla_powerwall": [
        "https://www.tesla.com/powerwall",
        "https://www.tesla.com/support/energy/powerwall",
    ],
    "enphase": [
        "https://enphase.com/homeowners",
        "https://enphase.com/homeowners/enlighten",
        "https://enphase.com/homeowners/storage",
    ],
    "solaredge": [
        "https://www.solaredge.com/us/products/monitoring",
        "https://www.solaredge.com/us/products/battery",
    ],
    "emporia": [
        "https://www.emporiaenergy.com/",
        "https://www.emporiaenergy.com/emporia-vue/",
    ],
    "sense": [
        "https://sense.com/",
        "https://sense.com/features/",
    ],
    "sunpower": [
        "https://us.sunpower.com/solar-panels",
        "https://us.sunpower.com/home-solar/solar-battery-storage",
    ],
    "generac": [
        "https://www.generac.com/clean-energy/pwrcell",
        "https://www.generac.com/clean-energy/pwrview",
    ],
    "span": [
        "https://www.span.io/",
        "https://www.span.io/panel",
    ],
}

SLEEP_SECS = 1.0
BASE_DIR   = Path(__file__).parents[2] / "data"
TEXT_DIR   = BASE_DIR / "raw" / "text" / "web_pages"


def scrape_app(name: str, urls: list[str], app: FirecrawlApp) -> None:
    log.info("=== Scraping web pages for: %s (%d URLs) ===", name, len(urls))
    out_dir = TEXT_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)

    pages = []
    for url in urls:
        try:
            doc = app.scrape(url, formats=["markdown"], only_main_content=True)
            content = (doc.markdown or "").strip()
            if not content:
                log.info("  [EMPTY] %s", url)
                continue
            meta = doc.metadata
            pages.append({
                "url":         url,
                "title":       (meta.title or "") if meta else "",
                "description": (meta.description or "") if meta else "",
                "content":     content,
                "chars":       len(content),
            })
            log.info("  [OK] %s - %d chars", url, len(content))
        except Exception as exc:
            log.warning("  [FAIL] %s - %s", url, exc)
        time.sleep(SLEEP_SECS)

    out_path = out_dir / "pages.json"
    out_path.write_text(
        json.dumps({
            "app":        name,
            "count":      len(pages),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "pages":      pages,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("  Saved %d pages -> %s", len(pages), out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape official EV app web pages via Firecrawl")
    parser.add_argument("--app", nargs="+", choices=list(APP_URLS.keys()),
                        help="Scrape specific apps only (default: all)")
    args = parser.parse_args()

    targets = {k: v for k, v in APP_URLS.items()
               if not args.app or k in args.app}

    fc = FirecrawlApp(api_key=os.environ["FIRECRAWL_API_KEY"])

    total_pages = sum(len(v) for v in targets.values())
    log.info("Scraping %d apps, %d pages total", len(targets), total_pages)

    for name, urls in targets.items():
        try:
            scrape_app(name, urls, fc)
        except Exception as exc:
            log.error("Unexpected error scraping %s: %s", name, exc)

    log.info("Done.")


if __name__ == "__main__":
    main()
