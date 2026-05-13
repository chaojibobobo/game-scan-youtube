# Game Scan YouTube

Daily YouTube monitor for new mobile game gameplay videos. Scans weighted channels every 24 hours, deduplicates against a persistent game library, and pushes a structured report to Feishu/Lark.

## What it does

- **Channel scanning** — Monitors a weighted list of YouTube channels for new gameplay uploads in your target genre
- **Deduplication** — Tracks all seen games and videos in JSON files, never reports the same content twice
- **Cross-reference** — When a new game appears, searches for coverage on other channels to detect testing/launch signals
- **Channel discovery** — Automatically finds and evaluates new channels during each scan
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

Edit `scripts/push_feishu.py` and fill in:

```python
APP_ID = "your_app_id"
APP_SECRET = "your_app_secret"
USER_OPEN_ID = "your_open_id"
```

Get these from [Feishu Open Platform](https://open.feishu.cn/app) → your app → Credentials.

### 3. Initialize state files

On first run, create a working directory with two JSON files:

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
      "note": "why this channel matters"
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

Tell Claude: "run slg-scout" or "check for new SLG videos" — the skill triggers automatically on relevant prompts.

## Weight system

| Weight | Meaning | Scan priority |
|--------|---------|---------------|
| 9-10 | Seed channels (user-confirmed) | Every run |
| 7-8 | High-quality, frequent content | Every run |
| 5-6 | Regular content | Every run |
| 3-4 | Occasional content | Light scan |
| 1-2 | Needs validation | Skip |

Weights auto-adjust: channels with new content get +1, channels silent for 3 runs get -1.

## Report format

Each game entry includes:

- Game name, developer, status (Early Access / CBT / Soft Launch)
- File size and platform
- Gameplay description
- Download link (Google Play / App Store)
- Video links sorted by upload date, newest first
- Cross-reference count (how many channels covered it)

## Requirements

- Claude Code CLI
- Feishu/Lark app with IM permissions
- Python 3.9+ with `requests`
