#!/usr/bin/env bash
# run_daily_once.sh - cron-safe daily wrapper for game-scan-youtube
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DATE="$(date +%Y-%m-%d)"
REPORT="$PROJECT_DIR/$DATE.md"
STAMP_DIR="$PROJECT_DIR/.run-stamps"
STAMP="$STAMP_DIR/$DATE.done"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$STAMP_DIR" "$LOG_DIR"

if [[ -f "$STAMP" || -s "$REPORT" ]]; then
  echo "[$(date +%Y-%m-%dT%H:%M:%S)] daily scan already completed for $DATE; skipping"
  exit 0
fi

"$SCRIPT_DIR/run_scan.sh" --date "$DATE"
touch "$STAMP"
