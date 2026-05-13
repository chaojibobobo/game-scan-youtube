---
name: game-scan-youtube
description: >
  Daily YouTube monitor for new mobile game gameplay videos in a target genre. Scans weighted
  channels via RSS feeds, finds videos uploaded in the last 24 hours, deduplicates against
  previously seen games, and delivers only genuinely new content. Pushes reports to Feishu/Lark.
  Use this skill whenever the user mentions game scouting, competitive intelligence, mobile game
  monitoring, new game discovery, gameplay video tracking, 竞品监控, 游戏调研, or wants to find
  gameplay videos of competing titles. Also use for "搜一下新游戏", daily game check, or any
  game market landscape query. This skill tracks channels and games across sessions to avoid
  showing the same content twice.
---

# Game Scan YouTube — 24h Incremental Monitor

Daily scan for **new** gameplay videos uploaded in the last 24 hours. Never show the user something they've already seen.

## Persistent State

Two files in `~/studio/_shared/game-scan-youtube/`:

- **`channels.json`** — weighted channel list (seed + discovered), each entry has `relevant_videos_7d` (int) tracking relevant videos published in the last 7 days, updated each scan
- **`seen_games.json`** — games already reported, with `first_seen`, `last_seen`, and `seen_videos`

Both are read at start, written at end. They persist across sessions.

### channels.json

```json
{
  "last_updated": "YYYY-MM-DD",
  "seed_channels": [
    {
      "id": "@channel-handle",
      "channel_id": "UCxxxxxxxxxxxxxxxxxxxxxx",
      "name": "Channel Display Name",
      "url": "https://www.youtube.com/@channel-handle",
      "title_pattern": "Game Name: Genre Gameplay Mobile Android",
      "weight": 10,
      "tags": ["genre-tag-1", "genre-tag-2"],
      "note": "why this channel is valuable",
      "relevant_videos_7d": 0
    }
  ],
  "discovered_channels": []
}
```

`channel_id` (UC... format) is required for RSS feed access. Find it via: `curl -s "https://m.youtube.com/@handle" | grep -oP 'channel_id=UC[^"&]+'`. If a channel returns 404, set `channel_id: null` and demote to weight 1.

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
      "status": "Early Access|CBT|Soft Launch|Launched|New",
      "tags": ["..."]
    }
  }
}
```

## Core Loop

```
1. Read channels.json + seen_games.json
2. Batch scan: sort channels by weight desc, process 5 per batch
   - Fetch RSS feed via curl: youtube.com/feeds/videos.xml?channel_id={channel_id}
   - Parse XML, filter entries with <published> in last 24h
   - Apply genre keyword filter to title + description
   - Duration check: read video page for candidates, skip < 10 min
   - On RSS error/empty: skip channel (no health penalty)
3. For each new game found:
   - YouTube cross-ref (WebSearch): find coverage on other channels
   - Google Play cross-ref: extract downloads, rating, last update
   - Channel discovery: evaluate new channels for discovered_channels
4. Dedup: filter out games/videos already in seen_games.json
   - New game → full entry with all details
   - Known game → only include video URLs not in seen_videos
5. Generate markdown report (newest upload first)
6. Update state:
   - seen_games.json: add new games, append new video URLs, update last_seen
   - channels.json: update relevant_videos_7d per channel, adjust weights per health rules
7. Push to Feishu:
   python3 scripts/push_feishu.py --date YYYY-MM-DD --dir ~/studio/_shared/game-scan-youtube
```

## Dedup Rules

- **Game already in seen_games.json?**
  - Check its `seen_videos` list
  - Only include video URLs NOT already in that list
  - Mark as "update" not "new discovery"
- **Game NOT in seen_games.json?**
  - This is a genuinely new find — full entry with all details
- **Video URL already in seen_games?** Skip it entirely

## Scan Strategy (24h window)

Only look for videos uploaded **today or yesterday**.

### Primary: YouTube RSS feeds

Each channel in channels.json has a `channel_id` (UC... format). Fetch the RSS feed to get structured video data with precise timestamps — no JS rendering, no rate limits, no cookie walls.

**URL format:** `https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}`

Each RSS feed returns the latest 15 videos as XML with:
- `<published>` — exact upload timestamp (ISO 8601)
- `<title>` — video title
- `<yt:videoId>` — video ID for URL construction
- `<media:statistics views="...">` — view count
- `<media:description>` — full description (for genre/size extraction)

**Fetch method:** Use `curl` via Bash (not webReader) to avoid IncompleteRead errors from chunked transfer encoding. Python's `urllib` can also fail on large feeds — `curl -s --max-time 30` is the most reliable.

**Filter pipeline:**
1. Parse XML, extract all `<entry>` elements
2. Keep only entries with `<published>` within last 24h
3. Filter by genre keywords in title/description (strategy, survival, base-building, RTS, 4X, etc.)
4. Exclude known irrelevant genres (RPG, racing, sports, puzzle, dress-up, etc.)
5. For remaining videos, check duration via video page read — skip < 10 min

**Adding a new channel:** When a new channel is added to channels.json, find its `channel_id` by reading `https://m.youtube.com/@handle` and extracting the UC... ID from page source (`grep -oP 'channel_id=UC[^"&]+'`).

### Fallback 1: WebSearch (cross-reference)

When RSS finds a potential new game, use WebSearch to verify coverage on other channels:
```
"[game name]" gameplay mobile android site:youtube.com
```
This also serves as channel discovery — if a new channel appears in results covering multiple games in your genre, add it to `discovered_channels`.

### Fallback 2: Channel page read (duration check)

RSS feeds don't include video duration. For candidate videos that pass the genre keyword filter, read the individual video page to check duration ≥ 10 min:
- `mcp__web_reader__webReader` on `https://m.youtube.com/watch?v={videoId}`
- Or curl + grep for `"lengthSeconds":"..."` in page source

### Batch processing

- Sort channels by weight descending, process in batches of 5
- Seed channels (weight 9-10) always in first batch
- No pacing needed between RSS requests (no rate limiting)
- If RSS returns empty/errors for a channel: skip it, no health penalty
- Update `relevant_videos_7d` for each channel after scanning

### Google Play signal

For new games, extract store metrics:
```
"[game name]" site:play.google.com
```
Extract: download count, rating, last update date. A sudden spike in downloads = scaling test signal.

### Channel discovery

If a cross-ref search reveals a new channel covering multiple games in your target genre:
1. Check if it's already in channels.json
2. Find its `channel_id` via `curl m.youtube.com/@handle | grep channel_id`
3. Evaluate: how many relevant videos in its RSS feed? Consistent title pattern?
4. Add to `discovered_channels` with `channel_id`, `relevant_videos_7d: 0` and appropriate initial weight

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

`relevant_videos_7d` is recalculated each scan: count how many of the channel's videos found in this run fall within the rolling 7-day window (not cumulative — reset and recount every run). This means a channel that was active last week but silent this week will correctly decay to 0.

Channel health (based on `relevant_videos_7d`, updated each run):
- `relevant_videos_7d` ≥ 5 → healthy, maintain weight
- `relevant_videos_7d` 1-4 → watching
- `relevant_videos_7d` = 0 AND weight > 5 → demote -1 (min 1), flag for user review

**Important:** channels skipped by batch processing (429/empty) do NOT update `relevant_videos_7d` and do NOT participate in health calculations. Only channels whose pages were actually read get updated.

## Output Format

Save to `~/studio/_shared/game-scan-youtube/YYYY-MM-DD.md`.

```markdown
# Game Scout — YYYY-MM-DD（24h Update）

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

If no new videos found in 24h, write a Quiet Day report with a **7-day summary** section. The quiet day push becomes an opportunity to deliver a weekly retrospective — this keeps the daily push valuable even when there's nothing new.

```markdown
# Game Scout — YYYY-MM-DD（24h Update）

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
- ...

#### By Discovery Date
- MM-DD: [list of games first seen that day]
- MM-DD: [list of games]

### Channels scanned today
[List channels checked]
```

**How to build the 7-day summary:** Read seen_games.json, filter games with `first_seen` in the last 7 days, sort by `len(seen_videos)` descending. Identify trends by grouping games by shared themes (developer region, genre tags, gameplay mechanics).

Don't fabricate content. A quiet day is honest data — the 7-day summary is derived from what was actually tracked.

## Sorting

- **Primary sort**: video upload time within 24h, newest first
- Include upload time (HH:MM) when available

## What counts

Include: CBT/soft launch/early access/just launched, actual gameplay footage, survival-strategy hybrids, RTS-strategy hybrids, core mechanics (base building, map, alliance, resource mgmt, PvP). Size > 500MB = more likely real game in your genre.

Exclude: established titles unless major update, pure RPG/survival without strategy layer, PC-only, trailers without gameplay.

**Duration filter: only include videos ≥ 10 minutes.** Gameplay videos under 10 min are usually trailers, clips, or shorts — not real gameplay deep-dives. When scanning, check duration and skip anything shorter.

## IM Push

The push script auto-reads the day's report + `seen_games.json` to build the Feishu message. No manual data entry needed.

```bash
# Normal push
python3 scripts/push_feishu.py --date YYYY-MM-DD --dir ~/studio/_shared/game-scan-youtube

# Dry run (print to stdout, don't send)
python3 scripts/push_feishu.py --date YYYY-MM-DD --dir ~/studio/_shared/game-scan-youtube --dry-run
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
- **RSS-first**: fetch RSS feeds for structured video data, WebSearch for cross-ref only.
- **Batch with pacing**: 5 channels per batch. RSS has no rate limit, but cross-ref WebSearch may 429 — space those out.
- **Automated push**: script auto-reads files and pushes, `--dry-run` for testing.
- **Cross-reference**: same game on 2+ channels in same day = hot new test.
- **Honest**: quiet day = quiet day. Don't pad.
- **Concise**: each entry 5-8 lines + video links. This is a daily digest, not a research report.
