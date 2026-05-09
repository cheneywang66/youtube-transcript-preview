#!/usr/bin/env python3
"""Fetch timestamped YouTube transcripts and save them as Markdown."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse


CHINESE_LANGS = ["zh-Hans", "zh-CN", "zh", "zh-Hant", "zh-TW"]
ENGLISH_LANGS = ["en", "en-US", "en-GB"]


def parse_video_id(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value

    parsed = urlparse(value)
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")

    if host.endswith("youtu.be") and path:
        return path.split("/")[0]

    if "youtube.com" in host:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
            if video_id:
                return video_id
        match = re.search(r"(?:embed|shorts|live)/([A-Za-z0-9_-]{11})", parsed.path)
        if match:
            return match.group(1)

    raise ValueError(f"Could not parse a YouTube video ID from: {value}")


def format_timestamp(seconds: float) -> str:
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def transcript_to_markdown(video_url: str, video_id: str, language: str, transcript: list[dict]) -> str:
    lines = [
        f"# YouTube Transcript: {video_id}",
        "",
        f"- Source: {video_url}",
        f"- Video ID: `{video_id}`",
        f"- Transcript language: `{language}`",
        "",
        "## Transcript",
        "",
    ]

    iterable = getattr(transcript, "snippets", transcript)
    for item in iterable:
        start = float(getattr(item, "start", item.get("start", 0)))
        raw_text = getattr(item, "text", item.get("text", ""))
        text = " ".join(str(raw_text).replace("\n", " ").split())
        if not text:
            continue
        lines.append(f"- [{format_timestamp(start)}](https://www.youtube.com/watch?v={video_id}&t={int(start)}s) {text}")

    lines.append("")
    return "\n".join(lines)


def _snippet_list(fetched):
    snippets = getattr(fetched, "snippets", None)
    if snippets is not None:
        return [{"text": s.text, "start": s.start} for s in snippets]
    return list(fetched)


def fetch_transcript(video_id: str):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: youtube-transcript-api. Install with: "
            "python3 -m pip install youtube-transcript-api"
        ) from exc

    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
    except TranscriptsDisabled as exc:
        raise SystemExit(f"Transcripts are disabled for video {video_id}") from exc

    for language in CHINESE_LANGS:
        try:
            transcript_obj = transcript_list.find_transcript([language])
            return language, _snippet_list(transcript_obj.fetch())
        except NoTranscriptFound:
            pass

    for language in ENGLISH_LANGS:
        try:
            transcript_obj = transcript_list.find_transcript([language])
            return language, _snippet_list(transcript_obj.fetch())
        except NoTranscriptFound:
            pass

    available = [
        {"language_code": item.language_code, "language": item.language, "generated": item.is_generated}
        for item in transcript_list
    ]
    raise SystemExit(
        "No Chinese or English transcript found. Available transcripts: "
        + json.dumps(available, ensure_ascii=False)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a timestamped YouTube transcript as Markdown.")
    parser.add_argument("url", help="YouTube URL or 11-character video ID")
    parser.add_argument("--out-dir", default=".", help="Directory for generated Markdown")
    args = parser.parse_args()

    try:
        video_id = parse_video_id(args.url)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    language, transcript = fetch_transcript(video_id)
    output_path = out_dir / f"{video_id}.transcript.{language}.md"
    output_path.write_text(
        transcript_to_markdown(args.url, video_id, language, transcript),
        encoding="utf-8",
    )

    result = {
        "video_id": video_id,
        "language": language,
        "is_chinese": language in CHINESE_LANGS,
        "path": str(output_path),
        "segments": len(transcript),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
