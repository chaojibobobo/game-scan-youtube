---
name: game-scan-youtube
description: >
  Daily YouTube monitor for new mobile game gameplay videos in a specific genre.
  Scans weighted channels, finds videos uploaded in the last 24 hours, deduplicates
  against previously seen games, and delivers only genuinely new content. Ships with
  Feishu/Lark IM push via a bundled script. Adaptable to any game genre (SLG, RPG,
  survival, etc.) by changing the filter criteria and seed channels.
  Use this skill whenever the user mentions game scouting, competitive intelligence,
  mobile game monitoring, new game discovery, gameplay video tracking,
  竞品监控, or wants to build a daily scan-and-push pipeline for mobile game videos.
  Also use for "搜一下新游戏", daily game check, or any game market landscape query.
---

# Game Scan YouTube — 24h Incremental Monitor

Daily scan for **new** gameplay videos uploaded in the last 24 hours in your target genre. Never show the user something they've already seen.

## Setup

On first run, create a working directory (default: `~/game-scan-youtube/`) and initialize two JSON files. The user should provide their seed channels — YouTube channels known to cover the target genre.

### channels.json

```json
{
  "last_updated": "YYYY-MM-DD",
  "seed_channels": [
    {
      "id": "@channel-handle",
      "name": "Channel Display Name",
      "url": "https://www.youtube.com/@channel-handle",
      "title_pattern": "Game Name: Genre Gameplay Mobile Android",
      "weight": 10,
      "tags": ["genre-tag-1", "genre-tag-2"],
      "note": "why this channel is valuable",
      "slg_videos_7d": 0
    }
  ],
  "discovered_channels": []
}
```

### seen_games.json

```json
{
  "last_updated": "YYYY-MM-DD",
  "games": {
    "Game Name": {
      "first_seen": "YYYY-MM-DD",
      "last_seen": "YYYY-MM-DD",
      "seen_videos": ["youtube-url-1"],
      "developer": "...",
      "status": "CBT|Soft Launch|Launched|Early Access",
      "tags": ["..."]
    }
  }
}
```

Both are read at start, written at end. They persist across sessions.

## Core Loop

```
1. Read channels.json + seen_games.json
2. Batch scan: sort channels by weight desc, process 5 per batch
   - Read channel /videos page via mcp__web_reader__webReader (m.youtube.com)
   - Extract videos uploaded in last 24h, filter by title pattern
   - Check duration ≥ 10 min, skip shorter
   - On 429/empty: skip channel (no health penalty)
   - Pause between batches
3. For each new game found:
   - YouTube cross-ref: search for coverage on other channels
   - Google Play cross-ref: extract downloads, rating, last update
   - Channel discovery: evaluate new channels for discovered_channels
4. Dedup: filter out games/videos already in seen_games.json
   - New game → full entry with all details
   - Known game → only include video URLs not in seen_videos
5. Generate markdown report (newest upload first)
6. Update state:
   - seen_games.json: add new games, append new video URLs, update last_seen
   - channels.json: update slg_videos_7d per channel, adjust weights per health rules
7. Push to IM:
   python3 scripts/push_feishu.py --date YYYY-MM-DD --dir ~/game-scan-youtube
```

## Dedup Rules

- **Game already in seen_games.json?** Check its `seen_videos` list. Only include video URLs NOT already in that list. Mark as "update" not "new discovery".
- **Game NOT in seen_games.json?** Full entry with all details — this is a genuinely new find.
- **Video URL already in seen_games?** Skip it entirely.

## Scan Strategy (24h window)

Only look for videos uploaded **today or yesterday**.

### Primary: Direct channel page read

Use `mcp__web_reader__webReader` to read channel video pages directly:

1. **Primary URL:** `https://m.youtube.com/@channel-handle/videos` (lightweight, bypasses cookie wall)
2. **Fallback URL:** `https://www.youtube.com/@channel-handle/videos?pbj=1`
3. Extract videos uploaded in the last 24h from page content
4. Filter by channel's known title pattern to extract game names
5. Check each video page for duration ≥ 10 min — skip shorter ones

### Batch processing + rate limiting

- Sort channels by weight descending, process in batches of 5
- Seed channels (weight 9-10) always in first batch
- Pause between batches to avoid 429 errors
- If a channel page returns empty or 429: mark it as skipped, retry next run
- Update `slg_videos_7d` for each channel after scanning

### Fallback: WebSearch

Only use WebSearch when a channel page cannot be read:
```
"@channel-handle" gameplay mobile android today OR yesterday
```

### Cross-reference for new games

When a new game name appears, do two lookups:

**YouTube cross-ref** — find other channels covering it:
```
"[game name]" gameplay mobile android site:youtube.com
```

**Google Play signal** — extract store metrics:
```
"[game name]" site:play.google.com
```
Extract: download count, rating, last update date. A sudden spike in downloads = scaling test signal.

### Channel discovery

If a cross-ref search reveals a new channel covering multiple games in your genre:
1. Check if it's already in channels.json
2. If not, evaluate: how many relevant videos does it have? Consistent title pattern?
3. Add to `discovered_channels` with `slg_videos_7d: 0` and appropriate initial weight

## Weight System

| Weight | Meaning | Scan frequency |
|--------|---------|---------------|
| 9-10 | Seed channels (user-confirmed) | Every run |
| 7-8 | High-quality, frequent content | Every run |
| 5-6 | Regular content | Every run |
| 3-4 | Occasional | Every run (light) |
| 1-2 | Needs validation | Skip unless time allows |

Weight adjustments per run:
- Channel has ≥1 new relevant video this run → weight +1 (max 8)
- User explicitly approves a channel → promote to seed, weight 10

Channel health (based on `slg_videos_7d`, updated each run):
- `slg_videos_7d` ≥ 5 → healthy, maintain weight
- `slg_videos_7d` 1-4 → watching
- `slg_videos_7d` = 0 AND weight > 5 → demote -1 (min 1), flag for user review

**Important:** channels skipped by batch processing (429/empty) do NOT update `slg_videos_7d` and do NOT participate in health calculations. Only channels whose pages were actually read get updated.

## Output Format

Save to `~/game-scan-youtube/YYYY-MM-DD.md`.

```markdown
# Game Scan — YYYY-MM-DD（24h Update）

## New Games

### HH:MM upload | [Game Name] — [hook]
- [Video Title](youtube-url) — Channel · Duration · Views

**Status:** Early Access / CBT / Soft Launch / Just Launched
**Developer:** ...
**Platform:** Android / iOS / Both
**What you'll see:** [2-3 sentences gameplay description]
**Download:** Google Play / App Store URL (if available)
**Store signal:** X downloads · ★Y.Z · updated MM-DD
**Cross-ref:** X channels covered this today

---

## New Videos for Known Games

### [Game Name] — new video
- [Video Title](youtube-url) — Channel · Duration · Views · uploaded HH:MM
[Brief note on what's new in this video compared to previous ones]

---

## Channel Updates
[New channels discovered, weight changes]

## Quiet Day
[If nothing new found — say so. Don't pad the report.]
```

### Empty day handling

If no new videos found in 24h, write a Quiet Day report with a **7-day summary** section. The quiet day push becomes an opportunity to deliver a weekly retrospective — keeping the daily push valuable even when there's nothing new.

```markdown
# Game Scan — YYYY-MM-DD（24h Update）

## Quiet Day
No new gameplay videos found in the last 24 hours.

### 7-Day Summary (MM-DD ~ MM-DD)

#### Overview
- X new games tracked
- Y videos monitored
- Z channels scanned

#### Hot Games (sorted by video count)
| Game | Developer | Videos | Signal |
|------|-----------|--------|--------|
| Game Name | Dev | N | 🔴/🟡 |

Signal: 🔴 = 3+ videos (strong testing/launch signal), 🟡 = 1-2 videos

#### Trend Themes
- [Observable trend 1, e.g. "survival+strategy hybrid concentration (Game A, B, C)"]
- [Observable trend 2]

#### By Discovery Date
- MM-DD: [list of games first seen that day]

### Channels scanned today
[List channels checked]
```

**How to build the 7-day summary:** Read seen_games.json, filter games with `first_seen` in the last 7 days, sort by `len(seen_videos)` descending. Identify trends by grouping games by shared themes (developer region, genre tags, gameplay mechanics).

Don't fabricate content. A quiet day is honest data — the 7-day summary is derived from what was actually tracked.

## Sorting

- **Primary sort**: video upload time within 24h, newest first
- Include upload time (HH:MM) when available

## What counts

Adapt the include/exclude criteria to your target genre. For SLG/4X strategy games:

**Include:** CBT/soft launch/early access/just launched, actual gameplay footage, survival-strategy hybrids, RTS-strategy hybrids, core mechanics (base building, map, alliance, resource mgmt, PvP). Size > 500MB = more likely real.

**Exclude:** established titles unless major update, pure RPG/survival without strategy layer, PC-only, trailers without gameplay.

**Duration filter: only include videos ≥ 10 minutes.** Videos under 10 min are usually trailers, clips, or shorts — not real gameplay deep-dives. When scanning, check duration and skip anything shorter.

## IM Push

The push script auto-reads the day's report + `seen_games.json` to build the Feishu message. No manual data entry needed.

```bash
# Normal push
python3 scripts/push_feishu.py --date YYYY-MM-DD --dir ~/game-scan-youtube

# Dry run (print to stdout, don't send)
python3 scripts/push_feishu.py --date YYYY-MM-DD --dir ~/game-scan-youtube --dry-run
```

Credentials are read from environment variables, not hardcoded:
- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_USER_OPEN_ID`

Store them in `~/.game-scan-youtube/.env` for auto-loading:
```
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
FEISHU_USER_OPEN_ID=your_open_id
```

## Daily Scheduling

Use CronCreate to auto-run daily:

- Time: 11:03 local time (off-minute to avoid load spikes)
- Prompt: run the game-scan-youtube skill
- CronCreate: `"3 11 * * *"`

## Key Principles

- **Incremental only**: never show previously seen content. seen_games.json is the truth.
- **24h window**: focus on what's new RIGHT NOW, not what was new last week.
- **Channel-first, page-read**: read channel /videos pages directly for data, WebSearch only as fallback.
- **Batch with pacing**: 5 channels per batch, respect rate limits, skipped channels don't affect health.
- **Automated push**: script auto-reads files and pushes, `--dry-run` for testing.
- **Cross-reference**: same game on 2+ channels in same day = hot signal.
- **Honest**: quiet day = quiet day. Don't pad.
- **Concise**: each entry 5-8 lines + video links. This is a daily digest, not a research report.
