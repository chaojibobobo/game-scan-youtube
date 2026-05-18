#!/usr/bin/env bash
# run_scan.sh — Non-interactive game-scan-youtube runner
# Usage: ./run_scan.sh [--date YYYY-MM-DD] [--dir PATH] [--dry-run] [--budget USD] [--force-push]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Defaults
DATE="$(date +%Y-%m-%d)"
WORK_DIR="$PROJECT_DIR"
ENV_FILE="$HOME/.game-scan-youtube/.env"
BUDGET="1.0"
DRY_RUN=""
FORCE_PUSH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --date)        DATE="$2"; shift 2 ;;
    --dir)         WORK_DIR="$2"; shift 2 ;;
    --env)         ENV_FILE="$2"; shift 2 ;;
    --budget)      BUDGET="$2"; shift 2 ;;
    --dry-run)     DRY_RUN="1"; shift ;;
    --force-push)  FORCE_PUSH="1"; shift ;;
    -h|--help)
      echo "Usage: $0 [--date YYYY-MM-DD] [--dir PATH] [--env PATH] [--budget USD] [--dry-run] [--force-push]"
      echo ""
      echo "  --force-push  If the report already exists, skip scanning and only retry the"
      echo "                Feishu push. Use this for cron fallback after a push failure."
      exit 0 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

cd "$WORK_DIR"

echo "[$(date +%Y-%m-%dT%H:%M:%S)] game-scan-youtube scan start — date=$DATE dir=$WORK_DIR force_push=$FORCE_PUSH"

# Load .env (for Feishu push, passed through to claude session)
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
  echo "Loaded env from $ENV_FILE"
else
  echo "Warning: .env not found at $ENV_FILE (Feishu push may fail)"
fi

# --- Force-push mode: skip scan, just retry the push ---
if [[ -n "$FORCE_PUSH" ]]; then
  REPORT="$WORK_DIR/$DATE.md"
  if [[ ! -s "$REPORT" ]]; then
    echo "[$(date +%Y-%m-%dT%H:%M:%S)] --force-push but no report found at $REPORT; cannot push"
    exit 1
  fi
  echo "[$(date +%Y-%m-%dT%H:%M:%S)] --force-push: retrying Feishu push for existing report"
  python3 "$SCRIPT_DIR/push_feishu.py" --date "$DATE" --dir "$WORK_DIR"
  EXIT_CODE=$?
  echo "[$(date +%Y-%m-%dT%H:%M:%S)] push result — exit=$EXIT_CODE"
  exit $EXIT_CODE
fi

# Build prompt
PROMPT="Run the game-scan-youtube skill for date $DATE. Process all scan-eligible channels via RSS, then run the expansion search queries from SKILL.md to catch new YouTube gameplay videos beyond the known channel list. Dedup against seen_games.json, generate the daily report, update state files, discover/add useful new channels, then push to Feishu."
if [[ -n "$DRY_RUN" ]]; then
  PROMPT="Run the game-scan-youtube skill for date $DATE. Process all scan-eligible channels via RSS, then run the expansion search queries from SKILL.md to catch new YouTube gameplay videos beyond the known channel list. Dedup against seen_games.json, generate the daily report, update state files, and discover/add useful new channels. Do NOT push to Feishu — skip the python push script."
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
