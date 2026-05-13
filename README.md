# Game Scan YouTube

Daily YouTube monitor for new mobile game gameplay videos. Scans weighted channels every 24 hours, deduplicates against a persistent game library, and pushes a structured report to Feishu/Lark.

## What it does

- **Channel scanning** — Monitors a weighted list of YouTube channels for new gameplay uploads in your target genre
- **Batch processing** — Reads channel pages directly (5 per batch), respects rate limits, skips on 429 errors
- **Deduplication** — Tracks all seen games and videos in JSON files, never reports the same content twice
- **Cross-reference** — When a new game appears, searches YouTube and Google Play for coverage metrics
- **Channel discovery** — Automatically finds and evaluates new channels during each scan
- **Channel health** — Tracks `slg_videos_7d` per channel, auto-promotes/demotes based on activity
- **IM push** — Sends a rich text report to Feishu/Lark with game info, gameplay description, download links, and video links
- **Quiet day fallback** — When no new videos are found, delivers a 7-day retrospective summary instead

## Setup

### 1. Install as a Claude Code skill

Copy the `SKILL.md` and `scripts/` into your skill directory:

```bash
mkdir -p ~/.claude/skills/game-scan-youtube/scripts
cp SKILL.md ~/.claude/skills/game-scan-youtube/
cp scripts/push_feishu.py ~/.claude/skills/game-scan-youtube/scripts/
```

### 2. Configure Feishu credentials

Create a `.env` file (default location: `~/.game-scan-youtube/.env`):

```
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
FEISHU_USER_OPEN_ID=your_open_id
```

Get these from [Feishu Open Platform](https://open.feishu.cn/app) → your app → Credentials.

### 3. Initialize state files

Create a working directory with two JSON files:

**channels.json** — Your seed channels:

```json
{
  "last_updated": "2026-01-01",
  "seed_channels": [
    {
      "id": "@channel-handle",
      "name": "Channel Name",
      "url": "https://www.youtube.com/@channel-handle",
      "title_pattern": "Game Name Gameplay Mobile Android",
      "weight": 10,
      "tags": ["strategy", "SLG"],
      "note": "why this channel matters",
      "slg_videos_7d": 0
    }
  ],
  "discovered_channels": []
}
```

**seen_games.json** — Start empty:

```json
{
  "last_updated": "2026-01-01",
  "games": {}
}
```

### 4. Run

Tell Claude: "run game-scan-youtube" or "check for new game videos" — the skill triggers automatically on relevant prompts.

## Push script

```bash
# Normal push
python3 scripts/push_feishu.py --date YYYY-MM-DD --dir ~/game-scan-youtube

# Dry run (print to stdout, don't send)
python3 scripts/push_feishu.py --date YYYY-MM-DD --dir ~/game-scan-youtube --dry-run
```

The script auto-reads the day's markdown report and `seen_games.json` — no manual data entry needed.

## Weight system

| Weight | Meaning | Scan frequency |
|--------|---------|---------------|
| 9-10 | Seed channels (user-confirmed) | Every run |
| 7-8 | High-quality, frequent content | Every run |
| 5-6 | Regular content | Every run |
| 3-4 | Occasional content | Light scan |
| 1-2 | Needs validation | Skip |

Channel health (based on `slg_videos_7d`, updated each run):
- `slg_videos_7d` ≥ 5 → healthy, maintain weight
- `slg_videos_7d` 1-4 → watching
- `slg_videos_7d` = 0 AND weight > 5 → demote -1 (min 1), flag for user review

Channels skipped due to rate limiting (429) do NOT affect health calculations.

## Report format

Each game entry includes:

- Game name, developer, status (Early Access / CBT / Soft Launch)
- Gameplay description
- Download link (Google Play / App Store)
- Store signal (downloads, rating, last update)
- Video links sorted by upload date, newest first
- Cross-reference count (how many channels covered it)

Quiet days include a 7-day retrospective with hot games table and trend themes.

## Requirements

- Claude Code CLI
- Feishu/Lark app with IM permissions
- Python 3.9+ with `requests`
