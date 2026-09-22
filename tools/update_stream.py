#!/usr/bin/env python3
"""Update stream-data.json from the public YouTube channel pages."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


CHANNEL_URL = "https://www.youtube.com/@ginenowa"
YOUTUBE_URL = "https://www.youtube.com"
OUTPUT = Path(__file__).resolve().parents[1] / "stream-data.json"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})

    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def fetch_initial_data(path: str) -> dict:
    html = fetch_html(f"{CHANNEL_URL}{path}")

    match = re.search(
        r"var ytInitialData = (\{.*?\});</script>",
        html,
    )

    if not match:
        raise RuntimeError(
            f"YouTube data was not found at {path or '/'}"
        )

    return json.loads(match.group(1))


def find_lockups(value: object) -> list[dict]:
    results: list[dict] = []

    if isinstance(value, dict):
        lockup = value.get("lockupViewModel")

        if (
            isinstance(lockup, dict)
            and lockup.get("contentType")
            == "LOCKUP_CONTENT_TYPE_VIDEO"
        ):
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


def is_live_now(lockup: dict) -> bool:
    serialized = json.dumps(lockup, ensure_ascii=False).upper()

    live_markers = (
        "BADGE_STYLE_TYPE_LIVE_NOW",
        "LIVE NOW",
        "ライブ配信中",
    )

    matched = [
        marker
        for marker in live_markers
        if marker in serialized
    ]

    if matched:
        print(
            f"LIVE判定: {video_title(lockup)}",
            file=sys.stderr,
        )
        print(
            f"一致したマーカー: {matched}",
            file=sys.stderr,
        )

    return bool(matched)


def get_publish_date(video_id: str) -> datetime:
    """
    Read the video's real publication/start date
    from the watch page.
    """
    html = fetch_html(
        f"{YOUTUBE_URL}/watch?v={video_id}"
    )

    patterns = (
        r'"publishDate":"([^"]+)"',
        r'"uploadDate":"([^"]+)"',
        r'<meta itemprop="datePublished" content="([^"]+)"',
    )

    for pattern in patterns:
        match = re.search(pattern, html)

        if not match:
            continue

        value = match.group(1)

        try:
            # Handles values such as:
            # 2026-09-22
            # 2026-09-22T13:00:00+00:00
            if "T" not in value:
                return datetime.fromisoformat(
                    value
                ).replace(tzinfo=timezone.utc)

            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed

        except ValueError:
            continue

    raise RuntimeError(
        f"Could not determine publish date for {video_id}"
    )


def video_data(
    lockup: dict,
    kind: str,
    published_at: datetime | None = None,
) -> dict:

    video_id = lockup.get("contentId")
    title = video_title(lockup)

    if not video_id or not title:
        raise RuntimeError(
            "YouTube returned a video without an ID or title"
        )

    data = {
        "kind": kind,
        "videoId": video_id,
        "title": title,
        "thumbnail":
            f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
    }

    if published_at:
        data["publishedAt"] = published_at.isoformat()

    return data


def latest_item(
    path: str,
    kind: str,
) -> tuple[dict, datetime] | None:

    lockups = find_lockups(
        fetch_initial_data(path)
    )

    if not lockups:
        return None

    # Tabs are normally newest-first.
    # We only need the newest valid item.
    for lockup in lockups:
        if is_live_now(lockup):
            continue

        video_id = lockup.get("contentId")

        if not video_id:
            continue

        try:
            published_at = get_publish_date(
                video_id
            )
        except Exception as error:
            print(
                f"Could not read date for "
                f"{video_id}: {error}",
                file=sys.stderr,
            )
            continue

        return (
            video_data(
                lockup,
                kind,
                published_at,
            ),
            published_at,
        )

    return None


def current_feature() -> dict:
    # ----------------------------------
    # 1. LIVE NOW always wins
    # ----------------------------------

    home_lockups = find_lockups(
        fetch_initial_data("")
    )

    active_live = next(
        (
            item
            for item in home_lockups
            if is_live_now(item)
        ),
        None,
    )

    if active_live:
        return video_data(
            active_live,
            "live",
        )

    # ----------------------------------
    # 2. Latest regular video
    # ----------------------------------

    latest_video = latest_item(
        "/videos",
        "video",
    )

    # ----------------------------------
    # 3. Latest completed stream
    # ----------------------------------

    latest_archive = latest_item(
        "/streams",
        "archive",
    )

    # ----------------------------------
    # 4. Compare them
    # ----------------------------------

    if latest_video and latest_archive:
        video_data_result, video_date = (
            latest_video
        )

        archive_data_result, archive_date = (
            latest_archive
        )

        if archive_date > video_date:
            return archive_data_result

        return video_data_result

    if latest_archive:
        return latest_archive[0]

    if latest_video:
        return latest_video[0]

    raise RuntimeError(
        "No videos or stream archives were found"
    )


def main() -> int:
    data = current_feature()

    previous = (
        json.loads(
            OUTPUT.read_text(
                encoding="utf-8"
            )
        )
        if OUTPUT.exists()
        else None
    )

    if data == previous:
        print(
            "Featured stream is unchanged."
        )
        return 0

    OUTPUT.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Featured {data['kind']} updated: "
        f"{data['title']}"
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())

    except Exception as error:
        print(
            f"Could not update featured stream: "
            f"{error}",
            file=sys.stderr,
        )

        raise SystemExit(1)