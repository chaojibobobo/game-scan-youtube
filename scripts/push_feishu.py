"""Push Game Scout report to Feishu/Lark IM.

Before first use, fill in your credentials below.
Get them from: https://open.feishu.cn/app → your app → Credentials & Basic Info
"""

import json
import sys
from datetime import date

import requests

# ====== CONFIGURE THESE ======
APP_ID = "YOUR_APP_ID"
APP_SECRET = "YOUR_APP_SECRET"
USER_OPEN_ID = "YOUR_USER_OPEN_ID"  # or use chat_id for group chats
BASE_URL = "https://open.feishu.cn/open-apis"
# ==============================

QUIET_DAY = False

# Report data — populate this each run before pushing
GAMES: list[dict] = []


def get_token() -> str:
    resp = requests.post(
        f"{BASE_URL}/auth/v3/tenant_access_token/internal/",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Token request failed: {data}")
    return data["tenant_access_token"]


def push_report():
    content_lines = []
    today = date.today().isoformat()

    if QUIET_DAY:
        content_lines.append([
            {"tag": "text", "text": f"Game Scout | {today}\n\n"},
        ])
        content_lines.append([
            {"tag": "text", "text": f"Quiet Day — no new gameplay videos (≥10 min) in the last 24h\n"},
        ])
        content_lines.append([
            {"tag": "text", "text": "\nLib stats: tracked games · channels monitored"},
        ])

        post_content = {
            "zh_cn": {
                "title": f"Game Scout | Quiet Day · {today}",
                "content": content_lines,
            }
        }
    else:
        content_lines.append([
            {"tag": "text", "text": f"Game Scout | {today}\nFound {len(GAMES)} new game(s)\n\n"},
        ])

        for game in GAMES:
            content_lines.append([
                {"tag": "text", "text": f"▶ {game['name']}"},
            ])
            content_lines.append([
                {"tag": "text",
                 "text": f"  {game['tags']} | {game['size']} | {game['status']} | Cross-ref: {game['cross_ref']}"},
            ])
            if game.get("developer") and game["developer"] != "Unknown":
                content_lines.append([
                    {"tag": "text", "text": f"  Developer: {game['developer']}"},
                ])
            if game.get("gameplay"):
                content_lines.append([
                    {"tag": "text", "text": f"  Gameplay: {game['gameplay']}"},
                ])
            if game.get("download_url"):
                content_lines.append([
                    {"tag": "text", "text": "  "},
                    {"tag": "a", "text": "Download", "href": game["download_url"]},
                ])
            for v in sorted(game["videos"], key=lambda x: x["uploaded"], reverse=True):
                content_lines.append([
                    {"tag": "text", "text": f"  uploaded {v['uploaded']} · {v['title']} · {v['views']} views  "},
                    {"tag": "a", "text": "Watch", "href": v["url"]},
                ])
            content_lines.append([{"tag": "text", "text": "\n"}])

        post_content = {
            "zh_cn": {
                "title": f"Game Scout | {len(GAMES)} new game(s)",
                "content": content_lines,
            }
        }

    token = get_token()
    resp = requests.post(
        f"{BASE_URL}/im/v1/messages",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        params={"receive_id_type": "open_id"},
        json={
            "receive_id": USER_OPEN_ID,
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
    print(f"Pushed successfully! message_id: {data['data']['message_id']}")


if __name__ == "__main__":
    push_report()
