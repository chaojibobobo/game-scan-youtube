"""Push Game Scout report to Feishu/Lark IM.

Usage:
  python3 push_feishu.py --date 2026-05-14
  python3 push_feishu.py --date 2026-05-14 --dry-run
  python3 push_feishu.py --date 2026-05-14 --dir ~/my-scout --env ~/my-scout/.env
"""

import json
import os
import re
import sys
import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

BASE_URL = "https://open.feishu.cn/open-apis"


def load_env(env_path: Optional[Path] = None):
    """Load credentials from .env file and/or environment variables."""
    if env_path and env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

    missing = []
    for key in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_USER_OPEN_ID"):
        if not os.environ.get(key):
            missing.append(key)
    if missing:
        print(f"Missing env vars: {', '.join(missing)}")
        sys.exit(1)


def get_token() -> str:
    resp = requests.post(
        f"{BASE_URL}/auth/v3/tenant_access_token/internal/",
        json={
            "app_id": os.environ["FEISHU_APP_ID"],
            "app_secret": os.environ["FEISHU_APP_SECRET"],
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Token request failed: {data}")
    return data["tenant_access_token"]


def parse_report(report_path: Path) -> dict:
    """Parse a daily markdown report into structured data."""
    text = report_path.read_text()
    result = {"is_quiet": False, "games": []}

    # Match new game sections: ### HH:MM upload | Game Name — hook
    game_blocks = re.split(r"\n### ", text)
    for block in game_blocks[1:]:  # skip content before first ###
        lines = block.strip().splitlines()
        if not lines:
            continue

        header = lines[0]
        # New game: "HH:MM upload | Game Name — hook" or "2026-05-12 | Game Name — hook"
        # Known game update: "Game Name — new video"
        # Format 1: "HH:MM | Game Name — hook" (with pipe)
        # Format 2: "Game Name — hook" (no pipe, no time prefix)
        new_game_match = re.match(r".*\|\s*(.+?)\s*—\s*(.+)", header)
        if not new_game_match:
            new_game_match = re.match(r"(.+?)\s*—\s*(.+)", header)
        if new_game_match:
            game_name = new_game_match.group(1).strip()
            hook = new_game_match.group(2).strip()
            is_update = False
        else:
            update_match = re.match(r"(.+?)\s*—\s*new video", header)
            if not update_match:
                continue
            game_name = update_match.group(1).strip()
            hook = "update"
            is_update = True

        game = {
            "name": game_name,
            "hook": hook,
            "is_update": is_update,
            "videos": [],
            "status": "",
            "developer": "",
            "platform": "",
            "gameplay": "",
            "download_url": "",
            "store_signal": "",
            "cross_ref": "",
        }

        for line in lines[1:]:
            # Video links: - [Title](url) — meta
            video_match = re.match(r"-\s+\[(.+?)\]\((https?://[^\s)]+)\)\s*—\s*(.+)", line)
            if video_match:
                game["videos"].append({
                    "title": video_match.group(1),
                    "url": video_match.group(2),
                    "meta": video_match.group(3).strip(),
                })
                continue

            # Metadata lines: **Key:** Value
            meta_match = re.match(r"\*\*(.+?):\*\*\s*(.+)", line)
            if meta_match:
                key = meta_match.group(1).lower().replace(" ", "_")
                val = meta_match.group(2).strip()
                field_map = {
                    "status": "status",
                    "developer": "developer",
                    "platform": "platform",
                    "what_you'll_see": "gameplay",
                    "download": "download_url",
                    "store_signal": "store_signal",
                    "cross-ref": "cross_ref",
                }
                mapped = field_map.get(key)
                if mapped:
                    game[mapped] = val

        if game["videos"] or game["name"]:
            result["games"].append(game)

    # Only mark as quiet if no games were parsed AND report contains Quiet Day header.
    # Reports can have both "## Quiet Day" and game updates (e.g. known-game new videos).
    if not result["games"] and "## Quiet Day" in text:
        result["is_quiet"] = True

    return result


def build_7day_summary(seen_games_path: Path, report_date: date, channels_path: Optional[Path] = None) -> dict:
    """Build 7-day summary from seen_games.json."""
    data = json.loads(seen_games_path.read_text())
    games = data.get("games", {})
    cutoff = report_date - timedelta(days=7)

    total_channels = 0
    if channels_path and channels_path.exists():
        ch = json.loads(channels_path.read_text())
        total_channels = len(ch.get("seed_channels", [])) + len(ch.get("discovered_channels", []))

    recent = []
    for name, info in games.items():
        first_str = info.get("first_seen", "")
        if not first_str:
            continue
        first = datetime.strptime(first_str, "%Y-%m-%d").date()
        if first >= cutoff:
            recent.append({
                "name": name,
                "developer": info.get("developer", "Unknown"),
                "videos": len(info.get("seen_videos", [])),
                "first_seen": info["first_seen"],
                "last_seen": info.get("last_seen", info["first_seen"]),
            })

    recent.sort(key=lambda g: g["videos"], reverse=True)

    return {
        "period": f"{cutoff.isoformat()[5:]} ~ {report_date.isoformat()[5:]}",
        "total_games": len(recent),
        "total_channels": total_channels,
        "hot_games": recent,
    }


def build_feishu_content(report_date: date, parsed: dict, summary: dict) -> dict:
    """Build Feishu post content."""
    content_lines = []
    today = report_date.isoformat()

    if parsed["is_quiet"]:
        s = summary
        content_lines.append([
            {"tag": "text", "text": f"游戏竞品监控 | {today}\nQuiet Day — 24h 内无新增视频（≥10 分钟）\n\n"},
        ])
        content_lines.append([
            {"tag": "text", "text": f"📊 过去 7 天汇总 ({s['period']})\n"},
        ])
        content_lines.append([
            {"tag": "text", "text": f"  {s['total_games']} 款新游戏 · {sum(g['videos'] for g in s['hot_games'])} 条视频 · {s['total_channels']} 个频道监控"},
        ])

        if s["hot_games"]:
            content_lines.append([
                {"tag": "text", "text": "\n🔥 高信号游戏（视频覆盖数）："},
            ])
            for g in s["hot_games"][:9]:
                signal = "🔴" if g["videos"] >= 3 else "🟡"
                content_lines.append([
                    {"tag": "text", "text": f"  {signal} {g['name']} ({g['developer']}) — {g['videos']} 条视频"},
                ])

        content_lines.append([
            {"tag": "text", "text": f"\n\n库状态：{s['total_games']} 款游戏 · {s['total_channels']} 个频道"},
        ])

        return {
            "zh_cn": {
                "title": f"Game Scout | Quiet Day · {today[5:]}",
                "content": content_lines,
            }
        }

    # Normal day
    games = parsed["games"]
    new_count = sum(1 for g in games if not g.get("is_update"))
    update_count = sum(1 for g in games if g.get("is_update"))
    parts = []
    if new_count:
        parts.append(f"{new_count} 款新游戏")
    if update_count:
        parts.append(f"{update_count} 款更新")
    header_text = "、".join(parts)
    content_lines.append([
        {"tag": "text", "text": f"游戏竞品监控 | {today}\n发现 {header_text}\n\n"},
    ])

    for game in games:
        prefix = "↻" if game.get("is_update") else "▶"
        content_lines.append([
            {"tag": "text", "text": f"{prefix} {game['name']}"},
        ])
        meta_parts = []
        if game.get("status"):
            meta_parts.append(game["status"])
        if game.get("cross_ref"):
            meta_parts.append(f"Cross-ref: {game['cross_ref']}")
        if meta_parts:
            content_lines.append([
                {"tag": "text", "text": f"  {' | '.join(meta_parts)}"},
            ])
        if game.get("developer") and game["developer"] != "Unknown":
            content_lines.append([
                {"tag": "text", "text": f"  Developer: {game['developer']}"},
            ])
        if game.get("gameplay"):
            content_lines.append([
                {"tag": "text", "text": f"  玩法: {game['gameplay']}"},
            ])
        if game.get("store_signal"):
            content_lines.append([
                {"tag": "text", "text": f"  Store: {game['store_signal']}"},
            ])
        if game.get("download_url"):
            # Extract URL from possible markdown [text](url) format
            url = game["download_url"]
            md_link = re.match(r"\[.*?\]\((https?://[^\s)]+)\)", url)
            if md_link:
                url = md_link.group(1)
            content_lines.append([
                {"tag": "text", "text": "  📦 "},
                {"tag": "a", "text": "Google Play", "href": url},
            ])
        for v in game.get("videos", []):
            content_lines.append([
                {"tag": "text", "text": f"  📹 {v['title']}  "},
                {"tag": "a", "text": "Watch", "href": v["url"]},
            ])
        content_lines.append([{"tag": "text", "text": "\n"}])

    return {
        "zh_cn": {
            "title": f"Game Scout | {header_text}",
            "content": content_lines,
        }
    }


def push_report(post_content: dict, dry_run: bool = False):
    """Send or dry-run the Feishu message."""
    if dry_run:
        title = post_content["zh_cn"]["title"]
        print(f"[DRY RUN] Title: {title}")
        for line_group in post_content["zh_cn"]["content"]:
            line_text = ""
            for item in line_group:
                t = item.get("text", "")
                href = item.get("href", "")
                if href:
                    line_text += f"{t}({href})"
                else:
                    line_text += t
            print(line_text)
        print()
        return

    token = get_token()
    resp = requests.post(
        f"{BASE_URL}/im/v1/messages",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        params={"receive_id_type": "open_id"},
        json={
            "receive_id": os.environ["FEISHU_USER_OPEN_ID"],
            "msg_type": "post",
            "content": json.dumps(post_content),
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        print(f"Send failed: {data}")
        sys.exit(1)
    print(f"Pushed! message_id: {data['data']['message_id']}")


def main():
    parser = argparse.ArgumentParser(description="Push Game Scout report to Feishu")
    parser.add_argument("--date", required=True, help="Report date (YYYY-MM-DD)")
    parser.add_argument("--dir", default="~/studio/_shared/game-scan-youtube", help="Working directory")
    parser.add_argument("--dry-run", action="store_true", help="Print message without sending")
    parser.add_argument("--env", default="~/.game-scan-youtube/.env", help="Path to .env file")
    args = parser.parse_args()

    work_dir = Path(args.dir).expanduser()
    env_path = Path(args.env).expanduser()
    report_date = datetime.strptime(args.date, "%Y-%m-%d").date()

    load_env(env_path)

    report_path = work_dir / f"{args.date}.md"
    if not report_path.exists():
        print(f"Report not found: {report_path}")
        sys.exit(1)

    seen_games_path = work_dir / "seen_games.json"
    if not seen_games_path.exists():
        print(f"seen_games.json not found: {seen_games_path}")
        sys.exit(1)

    parsed = parse_report(report_path)
    channels_path = work_dir / "channels.json"
    summary = build_7day_summary(seen_games_path, report_date, channels_path)
    post_content = build_feishu_content(report_date, parsed, summary)
    push_report(post_content, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
