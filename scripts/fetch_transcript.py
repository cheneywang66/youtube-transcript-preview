#!/usr/bin/env python3
"""Fetch timestamped YouTube transcripts and save them as Markdown."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse


CHINESE_LANGS = ["zh-Hans", "zh-CN", "zh", "zh-Hant", "zh-TW"]
ENGLISH_LANGS = ["en", "en-US", "en-GB"]
PREFERRED_LANGS = CHINESE_LANGS + ENGLISH_LANGS
WATCH_URL = "https://www.youtube.com/watch?v={video_id}"
INNERTUBE_API_URL = "https://www.youtube.com/youtubei/v1/player?key={api_key}"
INNERTUBE_CONTEXT = {"client": {"clientName": "ANDROID", "clientVersion": "20.10.38"}}
YOUTUBE_TRANSCRIPT_IO_API_URL = "https://www.youtube-transcript.io/api/transcripts"
YOUTUBE_TRANSCRIPT_IO_TOKEN_ENV = "YOUTUBE_TRANSCRIPT_IO_API_TOKEN"
REQUEST_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}
VIDEO_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{11}")


@dataclass
class TranscriptResult:
    language_code: str
    language_name: str
    is_generated: bool | None
    selection: str
    transcript: list[dict]


class TranscriptFetchError(RuntimeError):
    pass


def _validate_video_id(video_id: str, original_value: str) -> str:
    if VIDEO_ID_PATTERN.fullmatch(video_id):
        return video_id
    raise ValueError(f"Could not parse a valid YouTube video ID from: {original_value}")


def parse_video_id(value: str) -> str:
    value = value.strip()
    if VIDEO_ID_PATTERN.fullmatch(value):
        return value

    parsed = urlparse(value)
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")

    if host.endswith("youtu.be") and path:
        return _validate_video_id(path.split("/")[0], value)

    if "youtube.com" in host:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
            if video_id:
                return _validate_video_id(video_id, value)
        match = re.search(r"(?:embed|shorts|live|v)/([A-Za-z0-9_-]{11})", parsed.path)
        if match:
            return match.group(1)

    raise ValueError(f"Could not parse a YouTube video ID from: {value}")


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _snippet_value(item, name: str, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def transcript_to_markdown(
    video_url: str,
    video_id: str,
    language: str,
    transcript: list[dict],
    *,
    language_name: str = "",
    is_generated: bool | None = None,
    selection: str = "",
) -> str:
    language_label = f"`{language}`"
    if language_name:
        language_label += f" ({language_name})"

    lines = [
        f"# YouTube Transcript: {video_id}",
        "",
        f"- Source: {video_url}",
        f"- Video ID: `{video_id}`",
        f"- Transcript language: {language_label}",
    ]

    if is_generated is not None:
        lines.append(f"- Transcript type: {'auto-generated' if is_generated else 'manual'}")
    if selection:
        lines.append(f"- Selection: {selection}")

    lines.extend([
        "",
        "## Transcript",
        "",
    ])

    iterable = getattr(transcript, "snippets", transcript)
    for item in iterable:
        start = float(_snippet_value(item, "start", 0))
        raw_text = _snippet_value(item, "text", "")
        text = " ".join(str(raw_text).replace("\n", " ").split())
        if not text:
            continue
        lines.append(f"- [{format_timestamp(start)}](https://www.youtube.com/watch?v={video_id}&t={int(start)}s) {text}")

    lines.append("")
    return "\n".join(lines)


def _snippet_list(fetched):
    snippets = getattr(fetched, "snippets", None)
    if snippets is not None:
        iterable = snippets
    else:
        iterable = fetched

    return [
        {
            "text": _snippet_value(snippet, "text", ""),
            "start": _snippet_value(snippet, "start", 0),
            "duration": _snippet_value(snippet, "duration", 0),
        }
        for snippet in iterable
    ]


def _available_transcripts(transcript_list):
    return [
        {
            "language_code": item.language_code,
            "language": item.language,
            "generated": item.is_generated,
            "translatable": item.is_translatable,
        }
        for item in transcript_list
    ]


def _select_transcript(transcript_list):
    try:
        return transcript_list.find_transcript(PREFERRED_LANGS), "preferred"
    except Exception as exc:
        if exc.__class__.__name__ != "NoTranscriptFound":
            raise

    for transcript_obj in transcript_list:
        return transcript_obj, "fallback-any-language"

    return None, "none"


def _request_proxies(http_proxy: str = "", https_proxy: str = ""):
    proxies = {}
    if http_proxy:
        proxies["http"] = http_proxy
    if https_proxy:
        proxies["https"] = https_proxy
    return proxies or None


def _decode_jsonish(value):
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            return json.loads(stripped)
    return value


def _looks_like_transcript_result(value) -> bool:
    if isinstance(value, list):
        return bool(value)
    if not isinstance(value, dict):
        return False
    transcript_keys = {"tracks", "transcript", "segments", "captions", "text"}
    return bool(transcript_keys.intersection(value))


def _service_field(value, *keys, default=None):
    if not isinstance(value, dict):
        return default
    for key in keys:
        if key in value and value[key] not in (None, ""):
            return value[key]
    return default


def _label_text(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        if "simpleText" in value:
            return str(value["simpleText"]).strip()
        runs = value.get("runs")
        if isinstance(runs, list):
            return "".join(str(run.get("text", "")) for run in runs if isinstance(run, dict)).strip()
    return ""


def _service_video_id(value) -> str:
    if not isinstance(value, dict):
        return ""
    return str(_service_field(value, "id", "videoId", "video_id", default="")).strip()


def _service_results(payload):
    payload = _decode_jsonish(payload)
    if isinstance(payload, dict) and "data" in payload and not _looks_like_transcript_result(payload):
        payload = _decode_jsonish(payload["data"])

    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("results", "items", "transcripts", "videos"):
            value = _decode_jsonish(payload.get(key))
            if isinstance(value, list):
                return value
        return [payload]

    return []


def _select_service_result(payload, video_id: str):
    results = _service_results(payload)
    for result in results:
        if _service_video_id(result) == video_id:
            return result

    for result in results:
        if _looks_like_transcript_result(result):
            return result

    return results[0] if results else None


def _looks_like_segment(value) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if not isinstance(value, dict):
        return False
    return any(key in value for key in ("text", "caption", "sentence", "utf8", "start", "duration", "startMs", "tStartMs"))


def _looks_like_segment_list(value) -> bool:
    return isinstance(value, list) and bool(value) and all(_looks_like_segment(item) for item in value[:3])


def _service_language_code(*values) -> str:
    for value in values:
        code = _service_field(value, "languageCode", "language_code", "lang", "code", default="")
        if code:
            return str(code)
        language = _service_field(value, "language", default="")
        if isinstance(language, str) and re.fullmatch(r"[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]+)?", language):
            return language.replace("_", "-")
    return "unknown"


def _service_language_name(*values) -> str:
    for value in values:
        name = _label_text(_service_field(value, "languageName", "language_name", "name", "label", default=""))
        if name:
            return name
        language = _service_field(value, "language", default="")
        if isinstance(language, str) and not re.fullmatch(r"[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]+)?", language):
            return language
    return ""


def _service_is_generated(*values):
    for value in values:
        generated = _service_field(value, "isGenerated", "is_generated", "generated", default=None)
        if isinstance(generated, bool):
            return generated
        if isinstance(generated, str) and generated.lower() in {"true", "false"}:
            return generated.lower() == "true"
        if _service_field(value, "kind", default="") == "asr":
            return True
    return None


def _select_service_track(result):
    if isinstance(result, list):
        return result, "direct"
    if not isinstance(result, dict):
        return result, "direct"

    tracks = _decode_jsonish(result.get("tracks"))
    if tracks is None:
        return result, "direct"

    if isinstance(tracks, dict):
        tracks = [tracks]

    if _looks_like_segment_list(tracks):
        return tracks, "direct-tracks"

    if not isinstance(tracks, list) or not tracks:
        return result, "empty-tracks"

    for language in PREFERRED_LANGS:
        for track in tracks:
            if _service_language_code(track) == language:
                return track, "preferred"

    return tracks[0], "fallback-any-language"


def _segment_text(segment) -> str:
    if isinstance(segment, str):
        return " ".join(segment.split())

    if not isinstance(segment, dict):
        return ""

    segments = segment.get("segs")
    if isinstance(segments, list):
        text = "".join(str(item.get("utf8", "")) for item in segments if isinstance(item, dict))
        if text.strip():
            return " ".join(html.unescape(text).split())

    for key in ("text", "caption", "sentence", "utf8", "value"):
        if key not in segment:
            continue
        value = segment[key]
        if isinstance(value, list):
            text = " ".join(str(item) for item in value)
        else:
            text = _label_text(value) or str(value)
        text = " ".join(html.unescape(text).split())
        if text:
            return text

    return ""


def _parse_time_value(value, default: float = 0) -> float:
    if value in (None, ""):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().rstrip("s")
        if not cleaned:
            return default
        if ":" in cleaned:
            parts = cleaned.split(":")
            try:
                total = 0.0
                for part in parts:
                    total = total * 60 + float(part)
                return total
            except ValueError:
                return default
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


def _segment_start(segment) -> float:
    if not isinstance(segment, dict):
        return 0
    for key in ("start", "startTime", "start_time", "offset", "offsetSeconds"):
        if key in segment:
            return _parse_time_value(segment[key])
    for key in ("startMs", "start_ms", "tStartMs", "offsetMs"):
        if key in segment:
            return _parse_time_value(segment[key]) / 1000
    return 0


def _segment_duration(segment) -> float:
    if not isinstance(segment, dict):
        return 0
    for key in ("duration", "dur", "durationSeconds"):
        if key in segment:
            return _parse_time_value(segment[key])
    for key in ("durationMs", "duration_ms", "dDurationMs"):
        if key in segment:
            return _parse_time_value(segment[key]) / 1000
    return 0


def _segment_source(track):
    track = _decode_jsonish(track)
    if isinstance(track, dict):
        for key in ("transcript", "segments", "captions", "items"):
            value = _decode_jsonish(track.get(key))
            if isinstance(value, list):
                return value
        if isinstance(track.get("text"), str):
            return [track]
    return track


def _normalize_service_segments(track) -> list[dict]:
    source = _segment_source(track)
    if isinstance(source, str):
        source = [{"text": source, "start": 0, "duration": 0}]
    if not isinstance(source, list):
        return []

    snippets = []
    for segment in source:
        text = _segment_text(segment)
        if not text:
            continue
        snippets.append(
            {
                "text": text,
                "start": _segment_start(segment),
                "duration": _segment_duration(segment),
            }
        )
    return snippets


def _normalize_youtube_transcript_io_result(payload, video_id: str) -> TranscriptResult:
    result = _select_service_result(payload, video_id)
    if result is None:
        raise TranscriptFetchError(f"youtube-transcript.io returned no result for video {video_id}")

    track, selection = _select_service_track(result)
    transcript = _normalize_service_segments(track)
    if not transcript:
        raise TranscriptFetchError(f"youtube-transcript.io returned no usable transcript segments for video {video_id}")

    return TranscriptResult(
        language_code=_service_language_code(track, result),
        language_name=_service_language_name(track, result),
        is_generated=_service_is_generated(track, result),
        selection=f"youtube-transcript-io-{selection}",
        transcript=transcript,
    )


def _json_value_after_marker(page_html: str, marker: str):
    marker_index = page_html.find(marker)
    if marker_index == -1:
        raise ValueError(f"Could not find {marker}")

    start = page_html.find("{", marker_index)
    if start == -1:
        raise ValueError(f"Could not find JSON start after {marker}")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(page_html)):
        char = page_html[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(page_html[start : index + 1])

    raise ValueError(f"Could not find JSON end after {marker}")


def _track_name(track) -> str:
    name = track.get("name", {})
    if "simpleText" in name:
        return name["simpleText"]
    return "".join(run.get("text", "") for run in name.get("runs", [])).strip()


def _select_caption_track(tracks):
    for language in PREFERRED_LANGS:
        for track in tracks:
            if track.get("languageCode") == language:
                return track, "preferred"

    if tracks:
        return tracks[0], "fallback-any-language"

    return None, "none"


def _caption_tracks_from_player_response(player_response):
    captions = player_response.get("captions", {})
    renderer = captions.get("playerCaptionsTracklistRenderer", {})
    return renderer.get("captionTracks", [])


def _extract_innertube_api_key(page_html: str) -> str:
    match = re.search(r'"INNERTUBE_API_KEY":\s*"([a-zA-Z0-9_-]+)"', page_html)
    if not match:
        raise ValueError("Could not find INNERTUBE_API_KEY")
    return match.group(1)


def _parse_caption_json3(payload: str):
    data = json.loads(payload)
    snippets = []
    for event in data.get("events", []):
        segments = event.get("segs")
        if not segments:
            continue
        text = "".join(segment.get("utf8", "") for segment in segments)
        text = html.unescape(text).strip()
        if not text:
            continue
        snippets.append(
            {
                "text": text,
                "start": float(event.get("tStartMs", 0)) / 1000,
                "duration": float(event.get("dDurationMs", 0)) / 1000,
            }
        )
    return snippets


def _parse_caption_xml(payload: str):
    root = ET.fromstring(payload)
    snippets = []

    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag not in {"text", "p"}:
            continue

        if "start" in element.attrib:
            start = float(element.attrib.get("start", 0))
            duration = float(element.attrib.get("dur", 0))
        else:
            start = float(element.attrib.get("t", 0)) / 1000
            duration = float(element.attrib.get("d", 0)) / 1000

        text = html.unescape("".join(element.itertext())).strip()
        if text:
            snippets.append({"text": text, "start": start, "duration": duration})

    return snippets


def _parse_caption_payload(payload: str):
    stripped = payload.lstrip()
    if stripped.startswith("{"):
        return _parse_caption_json3(stripped)
    return _parse_caption_xml(payload)


def fetch_transcript_with_api(video_id: str, *, http_proxy: str = "", https_proxy: str = "") -> TranscriptResult:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            CouldNotRetrieveTranscript,
            RequestBlocked,
            TranscriptsDisabled,
        )
        from youtube_transcript_api.proxies import GenericProxyConfig
        from requests.exceptions import RequestException
    except ImportError as exc:
        raise TranscriptFetchError(
            "Missing dependency: youtube-transcript-api. Install with: "
            "python3 -m pip install youtube-transcript-api"
        ) from exc

    proxy_config = None
    if http_proxy or https_proxy:
        proxy_config = GenericProxyConfig(http_url=http_proxy or None, https_url=https_proxy or None)

    try:
        api = YouTubeTranscriptApi(proxy_config=proxy_config)
        transcript_list = api.list(video_id)
    except TranscriptsDisabled as exc:
        raise TranscriptFetchError(f"Transcripts are disabled for video {video_id}") from exc
    except RequestBlocked as exc:
        raise TranscriptFetchError(
            "YouTube blocked the transcript request for this network/IP. "
            "Try again later or pass --http-proxy/--https-proxy with a reliable residential proxy.\n"
            f"{exc}"
        ) from exc
    except CouldNotRetrieveTranscript as exc:
        raise TranscriptFetchError(f"Could not retrieve transcript metadata for video {video_id}:\n{exc}") from exc
    except RequestException as exc:
        raise TranscriptFetchError(f"Network error while contacting YouTube for video {video_id}: {exc}") from exc

    transcript_obj, selection = _select_transcript(transcript_list)
    if transcript_obj is None:
        raise TranscriptFetchError(f"No transcripts found for video {video_id}")

    try:
        fetched = transcript_obj.fetch()
    except RequestBlocked as exc:
        raise TranscriptFetchError(
            "YouTube blocked the transcript download for this network/IP. "
            "Try again later or pass --http-proxy/--https-proxy with a reliable residential proxy.\n"
            f"{exc}"
        ) from exc
    except CouldNotRetrieveTranscript as exc:
        available = json.dumps(_available_transcripts(transcript_list), ensure_ascii=False)
        raise TranscriptFetchError(
            f"Could not download transcript {transcript_obj.language_code} for video {video_id}.\n"
            f"Available transcripts: {available}\n{exc}"
        ) from exc
    except RequestException as exc:
        raise TranscriptFetchError(f"Network error while downloading transcript for video {video_id}: {exc}") from exc

    return TranscriptResult(
        language_code=transcript_obj.language_code,
        language_name=transcript_obj.language,
        is_generated=transcript_obj.is_generated,
        selection=f"api-{selection}",
        transcript=_snippet_list(fetched),
    )


def fetch_transcript_from_page(video_id: str, *, http_proxy: str = "", https_proxy: str = "") -> TranscriptResult:
    try:
        import requests
        from requests.exceptions import RequestException
    except ImportError as exc:
        raise TranscriptFetchError("Missing dependency: requests. Install youtube-transcript-api or requests.") from exc

    proxies = _request_proxies(http_proxy, https_proxy)
    try:
        page_response = requests.get(
            WATCH_URL.format(video_id=video_id),
            headers=REQUEST_HEADERS,
            proxies=proxies,
            timeout=20,
        )
        page_response.raise_for_status()
    except RequestException as exc:
        raise TranscriptFetchError(f"Could not fetch YouTube watch page for video {video_id}: {exc}") from exc

    try:
        api_key = _extract_innertube_api_key(page_response.text)
        player_response = requests.post(
            INNERTUBE_API_URL.format(api_key=api_key),
            headers=REQUEST_HEADERS,
            json={"context": INNERTUBE_CONTEXT, "videoId": video_id},
            proxies=proxies,
            timeout=20,
        )
        player_response.raise_for_status()
        tracks = _caption_tracks_from_player_response(player_response.json())
    except (ValueError, json.JSONDecodeError, RequestException) as exc:
        try:
            page_player_response = _json_value_after_marker(page_response.text, "ytInitialPlayerResponse")
            tracks = _caption_tracks_from_player_response(page_player_response)
        except (ValueError, json.JSONDecodeError) as page_exc:
            raise TranscriptFetchError(
                f"Could not parse captionTracks from YouTube page/player data for video {video_id}: "
                f"{exc}; page fallback: {page_exc}"
            ) from page_exc

    track, selection = _select_caption_track(tracks)
    if track is None:
        raise TranscriptFetchError(f"No captionTracks exposed in YouTube page/player data for video {video_id}")

    caption_url = track.get("baseUrl")
    if not caption_url:
        raise TranscriptFetchError(f"Selected caption track has no baseUrl for video {video_id}")

    try:
        caption_response = requests.get(caption_url, headers=REQUEST_HEADERS, proxies=proxies, timeout=20)
        caption_response.raise_for_status()
    except RequestException as exc:
        raise TranscriptFetchError(f"Could not download caption track for video {video_id}: {exc}") from exc

    try:
        transcript = _parse_caption_payload(caption_response.text)
    except (ET.ParseError, json.JSONDecodeError, ValueError) as exc:
        raise TranscriptFetchError(f"Could not parse caption payload for video {video_id}: {exc}") from exc

    if not transcript:
        raise TranscriptFetchError(f"Caption track downloaded but contained no usable segments for video {video_id}")

    return TranscriptResult(
        language_code=track.get("languageCode", "unknown"),
        language_name=_track_name(track),
        is_generated=track.get("kind") == "asr",
        selection=f"page-{selection}",
        transcript=transcript,
    )


def fetch_transcript_from_youtube_transcript_io(
    video_id: str,
    *,
    api_token: str = "",
    http_proxy: str = "",
    https_proxy: str = "",
) -> TranscriptResult:
    if not api_token:
        raise TranscriptFetchError(
            f"Missing youtube-transcript.io API token. Set {YOUTUBE_TRANSCRIPT_IO_TOKEN_ENV} "
            "or pass --youtube-transcript-io-token."
        )

    try:
        import requests
        from requests.exceptions import RequestException
    except ImportError as exc:
        raise TranscriptFetchError("Missing dependency: requests. Install youtube-transcript-api or requests.") from exc

    proxies = _request_proxies(http_proxy, https_proxy)
    try:
        response = requests.post(
            YOUTUBE_TRANSCRIPT_IO_API_URL,
            headers={
                "Authorization": f"Basic {api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={"ids": [video_id]},
            proxies=proxies,
            timeout=30,
        )
    except RequestException as exc:
        raise TranscriptFetchError(f"Network error while contacting youtube-transcript.io for video {video_id}: {exc}") from exc

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "")
        retry_message = f" Retry after {retry_after} seconds." if retry_after else ""
        raise TranscriptFetchError(f"youtube-transcript.io rate limit reached for video {video_id}.{retry_message}")

    try:
        response.raise_for_status()
    except RequestException as exc:
        detail = response.text.strip()
        if len(detail) > 500:
            detail = detail[:500] + "..."
        raise TranscriptFetchError(
            f"youtube-transcript.io request failed for video {video_id}: HTTP {response.status_code}. {detail}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        try:
            payload = _decode_jsonish(response.text)
        except json.JSONDecodeError:
            raise TranscriptFetchError(
                f"youtube-transcript.io returned non-JSON response for video {video_id}: "
                f"{response.text.strip()[:500]}"
            ) from exc
        if isinstance(payload, str):
            raise TranscriptFetchError(
                f"youtube-transcript.io returned non-JSON response for video {video_id}: "
                f"{payload.strip()[:500]}"
            ) from exc

    return _normalize_youtube_transcript_io_result(payload, video_id)


def fetch_transcript(
    video_id: str,
    *,
    http_proxy: str = "",
    https_proxy: str = "",
    method: str = "auto",
    youtube_transcript_io_token: str = "",
) -> TranscriptResult:
    errors = []
    api_token = youtube_transcript_io_token or os.environ.get(YOUTUBE_TRANSCRIPT_IO_TOKEN_ENV, "")

    if method in {"auto", "api"}:
        try:
            return fetch_transcript_with_api(video_id, http_proxy=http_proxy, https_proxy=https_proxy)
        except TranscriptFetchError as exc:
            if method == "api":
                raise SystemExit(str(exc)) from exc
            errors.append(f"api: {exc}")

    if method in {"auto", "page"}:
        try:
            return fetch_transcript_from_page(video_id, http_proxy=http_proxy, https_proxy=https_proxy)
        except TranscriptFetchError as exc:
            if method == "page":
                raise SystemExit(str(exc)) from exc
            errors.append(f"page: {exc}")

    if method in {"auto", "io", "youtube-transcript-io"} and api_token:
        try:
            return fetch_transcript_from_youtube_transcript_io(
                video_id,
                api_token=api_token,
                http_proxy=http_proxy,
                https_proxy=https_proxy,
            )
        except TranscriptFetchError as exc:
            if method in {"io", "youtube-transcript-io"}:
                raise SystemExit(str(exc)) from exc
            errors.append(f"youtube-transcript.io: {exc}")
    elif method in {"io", "youtube-transcript-io"}:
        raise SystemExit(
            f"Missing youtube-transcript.io API token. Set {YOUTUBE_TRANSCRIPT_IO_TOKEN_ENV} "
            "or pass --youtube-transcript-io-token."
        )

    raise SystemExit("Could not fetch a transcript.\n" + "\n\n".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a timestamped YouTube transcript as Markdown.")
    parser.add_argument("url", help="YouTube URL or 11-character video ID")
    parser.add_argument("--out-dir", default=".", help="Directory for generated Markdown")
    parser.add_argument("--http-proxy", default="", help="Optional HTTP proxy URL")
    parser.add_argument("--https-proxy", default="", help="Optional HTTPS proxy URL")
    parser.add_argument(
        "--youtube-transcript-io-token",
        default=os.environ.get(YOUTUBE_TRANSCRIPT_IO_TOKEN_ENV, ""),
        help=f"youtube-transcript.io API token. Prefer setting {YOUTUBE_TRANSCRIPT_IO_TOKEN_ENV}.",
    )
    parser.add_argument(
        "--method",
        choices=["auto", "io", "youtube-transcript-io", "api", "page"],
        default="auto",
        help=(
            "Transcript fetch method. auto tries free methods first (youtube-transcript-api, "
            "then the YouTube page captionTracks fallback), and falls back to youtube-transcript.io when a token is configured."
        ),
    )
    args = parser.parse_args()

    try:
        video_id = parse_video_id(args.url)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    result = fetch_transcript(
        video_id,
        http_proxy=args.http_proxy,
        https_proxy=args.https_proxy,
        method=args.method,
        youtube_transcript_io_token=args.youtube_transcript_io_token,
    )
    safe_language = re.sub(r"[^A-Za-z0-9_.-]+", "-", result.language_code)
    output_path = out_dir / f"{video_id}.transcript.{safe_language}.md"
    video_url = WATCH_URL.format(video_id=video_id)
    output_path.write_text(
        transcript_to_markdown(
            video_url,
            video_id,
            result.language_code,
            result.transcript,
            language_name=result.language_name,
            is_generated=result.is_generated,
            selection=result.selection,
        ),
        encoding="utf-8",
    )

    response = {
        "video_id": video_id,
        "language": result.language_code,
        "language_name": result.language_name,
        "is_chinese": result.language_code in CHINESE_LANGS,
        "is_generated": result.is_generated,
        "selection": result.selection,
        "path": str(output_path),
        "segments": len(result.transcript),
    }
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
