#!/usr/bin/env bash
# Runs automatically on first boot via Droplet user_data (cloud-init).
# Sets up the Python pipeline environment on Ubuntu 24.04.
set -euo pipefail
exec > /var/log/bootstrap.log 2>&1

echo "=== EV Research bootstrap started at $(date) ==="

# -- System packages -----------------------------------------------------------
apt-get update -qq
apt-get install -y -qq \
  python3.12 python3.12-venv python3-pip \
  postgresql-client \
  git curl unzip \
  ffmpeg                  # needed by yt-dlp for audio extraction

# -- Node.js 20 (for app-store / play-store scrapers) -------------------------
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# -- App directory -------------------------------------------------------------
APP=/opt/ev-pipeline
mkdir -p "$APP"

# -- Python venv ---------------------------------------------------------------
python3.12 -m venv "$APP/.venv"
source "$APP/.venv/bin/activate"

pip install --quiet --upgrade pip wheel

pip install --quiet \
  openai \
  anthropic \
  psycopg2-binary \
  pgvector \
  boto3 \
  praw \
  youtube-transcript-api \
  yt-dlp \
  firecrawl-py \
  apify-client \
  newsapi-python \
  feedparser \
  tiktoken \
  python-dotenv \
  httpx \
  tenacity \
  tqdm \
  fastapi \
  uvicorn[standard] \
  streamlit

# -- Node scraper packages -----------------------------------------------------
npm install -g app-store-scraper google-play-scraper

# -- Cron job - run pipeline at 02:00 daily ------------------------------------
CRON_LINE="0 2 * * * source $APP/.venv/bin/activate && python $APP/pipeline/run_all.py >> /var/log/ev-pipeline.log 2>&1"
(crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -

# -- Placeholder pipeline runner (overwritten when code is deployed) -----------
mkdir -p "$APP/pipeline"
cat > "$APP/pipeline/run_all.py" << 'PYEOF'
#!/usr/bin/env python3
"""Placeholder - replaced by actual pipeline code after deployment."""
import datetime, sys
print(f"[{datetime.datetime.utcnow().isoformat()}] Pipeline not yet deployed.", flush=True)
sys.exit(0)
PYEOF

echo "=== Bootstrap complete at $(date) ==="
