#!/usr/bin/env python3
"""Update stream-data.json from the public YouTube channel pages."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen


CHANNEL_URL = "https://www.youtube.com/@ginenowa"
OUTPUT = Path(__file__).resolve().parents[1] / "stream-data.json"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def fetch_initial_data(path: str) -> dict:
    request = Request(f"{CHANNEL_URL}{path}", headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8")

    match = re.search(r"var ytInitialData = (\{.*?\});</script>", html)
    if not match:
        raise RuntimeError(f"YouTube data was not found at {path or '/'}")
    return json.loads(match.group(1))


def find_lockups(value: object) -> list[dict]:
    results: list[dict] = []
    if isinstance(value, dict):
        lockup = value.get("lockupViewModel")
        if isinstance(lockup, dict) and lockup.get("contentType") == "LOCKUP_CONTENT_TYPE_VIDEO":
            results.append(lockup)
        for child in value.values():
            results.extend(find_lockups(child))
    elif isinstance(value, list):
        for child in value:
            results.extend(find_lockups(child))
    return results


def video_title(lockup: dict) -> str:
    return (
        lockup.get("metadata", {})
        .get("lockupMetadataViewModel", {})
        .get("title", {})
        .get("content", "")
    )


def video_data(lockup: dict, kind: str) -> dict:
    video_id = lockup.get("contentId")
    title = video_title(lockup)
    if not video_id or not title:
        raise RuntimeError("YouTube returned a video without an ID or title")
    return {
        "kind": kind,
        "videoId": video_id,
        "title": title,
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
    }


def is_live_now(lockup: dict) -> bool:
    # Waiting rooms use UPCOMING badges. Only these live-now markers trigger a switch.
    serialized = json.dumps(lockup, ensure_ascii=False).upper()
    live_markers = (
        "BADGE_STYLE_TYPE_LIVE_NOW",
        "THUMBNAIL_OVERLAY_BADGE_STYLE_LIVE",
        "LIVE NOW",
        "ライブ配信中",
    )
    return any(marker in serialized for marker in live_markers)


def current_feature() -> dict:
    home_lockups = find_lockups(fetch_initial_data(""))
    active_live = next((item for item in home_lockups if is_live_now(item)), None)
    if active_live:
        return video_data(active_live, "live")

    video_lockups = find_lockups(fetch_initial_data("/videos"))
    if not video_lockups:
        raise RuntimeError("No regular videos were found")
    # The Videos tab excludes Shorts and completed live streams and is newest-first.
    return video_data(video_lockups[0], "video")


def main() -> int:
    data = current_feature()
    previous = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else None
    if data == previous:
        print("Featured stream is unchanged.")
        return 0
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Featured {data['kind']} updated: {data['title']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Could not update featured stream: {error}", file=sys.stderr)
        raise SystemExit(1)
