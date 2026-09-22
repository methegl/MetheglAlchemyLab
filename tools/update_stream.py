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
    request = Request(
        f"{CHANNEL_URL}{path}",
        headers={"User-Agent": USER_AGENT},
    )

    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8")

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


def video_data(lockup: dict, kind: str) -> dict:
    video_id = lockup.get("contentId")
    title = video_title(lockup)

    if not video_id or not title:
        raise RuntimeError(
            "YouTube returned a video without an ID or title"
        )

    return {
        "kind": kind,
        "videoId": video_id,
        "title": title,
        "thumbnail":
            f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
    }


def is_live_now(lockup: dict) -> bool:
    """
    現在本当に配信中の動画だけを判定する。
    待機枠と配信アーカイブは除外する。
    """
    serialized = json.dumps(
        lockup,
        ensure_ascii=False,
    ).upper()

    # 待機枠を除外
    upcoming_markers = (
        "UPCOMING",
        "配信予定",
        "公開予定",
    )

    if any(
        marker in serialized
        for marker in upcoming_markers
    ):
        return False

    # 現在配信中を示すマーカー
    live_markers = (
        "BADGE_STYLE_TYPE_LIVE_NOW",
        "LIVE NOW",
        "ライブ配信中",
    )

    return any(
        marker in serialized
        for marker in live_markers
    )


def relative_age_seconds(lockup: dict) -> int:
    """
    YouTube一覧に表示される相対時刻を秒数に変換する。

    例:
    2h ago
    Streamed 2h ago
    3 weeks ago
    Streamed 2 hours ago

    数字が小さいほど新しい。
    """
    rows = (
        lockup.get("metadata", {})
        .get("lockupMetadataViewModel", {})
        .get("metadata", {})
        .get("contentMetadataViewModel", {})
        .get("metadataRows", [])
    )

    texts: list[str] = []

    for row in rows:
        for part in row.get("metadataParts", []):
            text = part.get("text", {})

            content = text.get("content", "")
            accessibility = text.get(
                "accessibilityLabel",
                "",
            )

            if content:
                texts.append(content)

            if accessibility:
                texts.append(accessibility)

    for text in texts:
        normalized = text.lower()

        match = re.search(
            r"(?:(?:streamed|premiered)\s+)?"
            r"(\d+)\s*"
            r"(second|minute|hour|day|week|month|year|"
            r"sec|min|hr|h|d|w|mo|yr)s?"
            r"\s+ago",
            normalized,
        )

        if not match:
            continue

        amount = int(match.group(1))
        unit = match.group(2)

        multipliers = {
            "second": 1,
            "sec": 1,

            "minute": 60,
            "min": 60,

            "hour": 60 * 60,
            "hr": 60 * 60,
            "h": 60 * 60,

            "day": 24 * 60 * 60,
            "d": 24 * 60 * 60,

            "week": 7 * 24 * 60 * 60,
            "w": 7 * 24 * 60 * 60,

            "month": 30 * 24 * 60 * 60,
            "mo": 30 * 24 * 60 * 60,

            "year": 365 * 24 * 60 * 60,
            "yr": 365 * 24 * 60 * 60,
        }

        return amount * multipliers[unit]

    raise RuntimeError(
        "Could not determine relative age for "
        f"{video_title(lockup)}"
    )


def current_feature() -> dict:
    # ==================================
    # 1. 現在配信中なら最優先
    # ==================================

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
        print(
            f"Live now: {video_title(active_live)}"
        )

        return video_data(
            active_live,
            "live",
        )

    # ==================================
    # 2. 最新の通常動画
    # ==================================

    video_lockups = find_lockups(
        fetch_initial_data("/videos")
    )

    latest_video = (
        video_lockups[0]
        if video_lockups
        else None
    )

    # ==================================
    # 3. 最新の配信アーカイブ
    # ==================================

    stream_lockups = find_lockups(
        fetch_initial_data("/streams")
    )

    latest_archive = (
        stream_lockups[0]
        if stream_lockups
        else None
    )

    # ==================================
    # 4. 動画とアーカイブを比較
    # ==================================

    if latest_video and latest_archive:
        video_age = relative_age_seconds(
            latest_video
        )

        archive_age = relative_age_seconds(
            latest_archive
        )

        print(
            f"Latest video: "
            f"{video_title(latest_video)} "
            f"({video_age}s ago)"
        )

        print(
            f"Latest archive: "
            f"{video_title(latest_archive)} "
            f"({archive_age}s ago)"
        )

        # 秒数が小さい方が新しい
        if archive_age < video_age:
            return video_data(
                latest_archive,
                "archive",
            )

        return video_data(
            latest_video,
            "video",
        )

    # ==================================
    # 5. 片方しか存在しない場合
    # ==================================

    if latest_archive:
        return video_data(
            latest_archive,
            "archive",
        )

    if latest_video:
        return video_data(
            latest_video,
            "video",
        )

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