#!/usr/bin/env bash
# run_scan.sh — Non-interactive game-scan-youtube runner
# Usage: ./run_scan.sh [--date YYYY-MM-DD] [--dir PATH] [--dry-run] [--budget USD]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Defaults
DATE="$(date +%Y-%m-%d)"
WORK_DIR="$PROJECT_DIR"
ENV_FILE="$HOME/.game-scan-youtube/.env"
BUDGET="1.0"
DRY_RUN=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --date)   DATE="$2"; shift 2 ;;
    --dir)    WORK_DIR="$2"; shift 2 ;;
    --env)    ENV_FILE="$2"; shift 2 ;;
    --budget) BUDGET="$2"; shift 2 ;;
    --dry-run) DRY_RUN="1"; shift ;;
    -h|--help)
      echo "Usage: $0 [--date YYYY-MM-DD] [--dir PATH] [--env PATH] [--budget USD] [--dry-run]"
      exit 0 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

echo "[$(date +%Y-%m-%dT%H:%M:%S)] game-scan-youtube scan start — date=$DATE dir=$WORK_DIR"

# Load .env (for Feishu push, passed through to claude session)
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
  echo "Loaded env from $ENV_FILE"
else
  echo "Warning: .env not found at $ENV_FILE (Feishu push may fail)"
fi

# Build prompt
PROMPT="Run the game-scan-youtube skill for date $DATE. Scan all channels via RSS, dedup against seen_games.json, generate the daily report, update state files, then push to Feishu."
if [[ -n "$DRY_RUN" ]]; then
  PROMPT="Run the game-scan-youtube skill for date $DATE. Scan all channels via RSS, dedup against seen_games.json, generate the daily report, update state files. Do NOT push to Feishu — skip the python push script."
fi

# Run claude in non-interactive mode
claude -p "$PROMPT" \
  --add-dir "$WORK_DIR" \
  --permission-mode bypassPermissions \
  --output-format json \
  --max-budget-usd "$BUDGET"

EXIT_CODE=$?

echo "[$(date +%Y-%m-%dT%H:%M:%S)] game-scan-youtube scan end — exit=$EXIT_CODE"
exit $EXIT_CODE
