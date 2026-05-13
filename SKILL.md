---
name: game-scan-youtube
description: >
  Daily YouTube monitor for new mobile game gameplay videos in a specific genre.
  Scans weighted channels, finds videos uploaded in the last 24 hours, deduplicates
  against previously seen games, and delivers only genuinely new content. Ships with
  Feishu/Lark IM push via a bundled script. Adaptable to any game genre (SLG, RPG,
  survival, etc.) by changing the filter criteria and seed channels.
  Use this skill whenever the user mentions game scouting, competitive intelligence,
  mobile game monitoring, new game discovery, gameplay video tracking, SLG竞品,
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
      "note": "why this channel is valuable"
    }
  ],
  "discovered_channels": []
}
```

### seen_games.json

```json
{
  "last_updated": "YYYY-MM-DD",
  "games": {}
}
```

Both are read at start, written at end. They persist across sessions.

## Core Loop

```
1. Read channels.json + seen_games.json
2. Scan high-weight channels for uploads in last 24h
3. Extract new game names from video titles
4. Cross-reference: search each new game to find more videos/channels
5. Filter: only include games/videos NOT in seen_games.json
6. For games already seen: only include NEW video URLs not in seen_games
7. Generate report (newest upload first)
8. Update seen_games.json and channels.json
9. Push to IM via bundled script
```

## Dedup Rules

- **Game already in seen_games.json?** Check its `seen_videos` list. Only include video URLs NOT already in that list. Mark as "update" not "new discovery".
- **Game NOT in seen_games.json?** Full entry with all details — this is a genuinely new find.
- **Video URL already in seen_games?** Skip it entirely.

## Scan Strategy (24h window)

Only look for videos uploaded **today or yesterday**. For each high-weight channel, search their recent content using queries like:

```
"@channel-handle" gameplay mobile android today
site:youtube.com "gameplay mobile android" "strategy" today OR yesterday
"new strategy game" mobile gameplay uploaded today
```

Extract game names from titles using the channel's known title pattern.

### Cross-reference for new games

When a new game name appears, search it:
```
"[game name]" gameplay mobile android site:youtube.com
```
This finds other channels covering it — both for cross-reference signal AND for channel discovery.

### Channel discovery

If a search reveals a new channel covering multiple games in your genre:
1. Check if it's already in channels.json
2. If not, evaluate: how many relevant videos does it have? Consistent title pattern?
3. Add to `discovered_channels` with appropriate initial weight

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
- Channel has 0 relevant content for 3 consecutive runs → weight -1 (min 1)
- User explicitly approves a channel → promote to seed, weight 10

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
[If nothing new found — include 7-day summary instead of leaving empty]
```

### Empty day handling

If no new videos found in 24h, write a Quiet Day report with a **7-day summary**. The quiet day push becomes a weekly retrospective — keeping the daily push valuable even when there's nothing new.

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

Use the bundled `scripts/push_feishu.py` to send the report to Feishu/Lark. Before first use, the user must configure their credentials in the script. Run it after generating the report:

```bash
python3 scripts/push_feishu.py
```

The script sends a rich text post with game name, tags, size, status, developer, gameplay description, download link, and video links sorted newest first.

## Key Principles

- **Incremental only**: never show previously seen content. seen_games.json is the truth.
- **24h window**: focus on what's new RIGHT NOW, not what was new last week.
- **Channel-first**: weighted channels are the primary discovery vector.
- **Cross-reference**: same game on 2+ channels in same day = hot signal.
- **Honest**: quiet day = quiet day. Don't pad.
- **Concise**: each entry 5-8 lines + video links. This is a daily digest, not a research report.
