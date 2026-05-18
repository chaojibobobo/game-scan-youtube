#!/usr/bin/env bash
# run_daily_once.sh - cron-safe daily wrapper for game-scan-youtube
# Uses done stamps for completion (not just report file existence).
# Includes concurrency protection via mkdir-based lock.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DATE="$(date +%Y-%m-%d)"
REPORT="$PROJECT_DIR/$DATE.md"
STAMP_DIR="$PROJECT_DIR/.run-stamps"
STAMP="$STAMP_DIR/$DATE.done"
LOCK_DIR="$PROJECT_DIR/.run-locks"
LOCK="$LOCK_DIR/$DATE.lock"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$STAMP_DIR" "$LOCK_DIR" "$LOG_DIR"

# --- Concurrency protection (atomic mkdir) ---
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "[$(date +%Y-%m-%dT%H:%M:%S)] another scan is running for $DATE (lock exists); exiting"
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

# --- Done stamp check (only reliable completion signal) ---
if [[ -f "$STAMP" ]]; then
  echo "[$(date +%Y-%m-%dT%H:%M:%S)] daily scan already completed for $DATE (done stamp exists); skipping"
  exit 0
fi

# --- Report exists but no stamp = scan ran but push may have failed ---
if [[ -s "$REPORT" ]]; then
  echo "[$(date +%Y-%m-%dT%H:%M:%S)] report exists for $DATE but no done stamp — retrying push only"
  "$SCRIPT_DIR/run_scan.sh" --date "$DATE" --force-push
  PUSH_EXIT=$?
  if [[ $PUSH_EXIT -eq 0 ]]; then
    touch "$STAMP"
    echo "[$(date +%Y-%m-%dT%H:%M:%S)] push retry succeeded for $DATE"
  else
    echo "[$(date +%Y-%m-%dT%H:%M:%S)] push retry failed (exit=$PUSH_EXIT); not writing done stamp"
  fi
  exit $PUSH_EXIT
fi

# --- No report and no stamp — run full scan ---
cd "$PROJECT_DIR"
"$SCRIPT_DIR/run_scan.sh" --date "$DATE"
SCAN_EXIT=$?

if [[ $SCAN_EXIT -ne 0 ]]; then
  echo "[$(date +%Y-%m-%dT%H:%M:%S)] scan failed (exit=$SCAN_EXIT); not writing done stamp"
  exit $SCAN_EXIT
fi

# --- Write done stamp only after successful scan (which includes Feishu push) ---
touch "$STAMP"
echo "[$(date +%Y-%m-%dT%H:%M:%S)] daily scan completed for $DATE"
