import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_transcript  # noqa: E402


class NoTranscriptFound(Exception):
    pass


class FakeTranscript:
    def __init__(self, language_code, language="Test Language", is_generated=False):
        self.language_code = language_code
        self.language = language
        self.is_generated = is_generated
        self.is_translatable = False


class FakeTranscriptList:
    video_id = "abc12345678"

    def __init__(self, transcripts, preferred=None):
        self.transcripts = transcripts
        self.preferred = preferred

    def __iter__(self):
        return iter(self.transcripts)

    def find_transcript(self, language_codes):
        if self.preferred is not None:
            return self.preferred
        raise NoTranscriptFound()


class Snippet:
    def __init__(self, text, start, duration):
        self.text = text
        self.start = start
        self.duration = duration


class FetchedTranscript:
    def __init__(self, snippets):
        self.snippets = snippets


class FetchTranscriptTests(unittest.TestCase):
    def test_parse_video_id_supports_common_url_shapes(self):
        self.assertEqual(fetch_transcript.parse_video_id("dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(fetch_transcript.parse_video_id("https://youtu.be/dQw4w9WgXcQ?t=1"), "dQw4w9WgXcQ")
        self.assertEqual(
            fetch_transcript.parse_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=abc"),
            "dQw4w9WgXcQ",
        )
        self.assertEqual(fetch_transcript.parse_video_id("https://www.youtube.com/v/dQw4w9WgXcQ"), "dQw4w9WgXcQ")

    def test_parse_video_id_rejects_invalid_ids_from_urls(self):
        invalid_values = [
            "not-a-valid-id",
            "https://youtu.be/not-a-valid-id",
            "https://www.youtube.com/watch?v=bad",
            "https://www.youtube.com/watch?v=too-long-video-id",
        ]

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    fetch_transcript.parse_video_id(value)

    def test_select_transcript_uses_preferred_languages_first(self):
        preferred = FakeTranscript("en", "English")
        transcript, selection = fetch_transcript._select_transcript(FakeTranscriptList([], preferred=preferred))
        self.assertIs(transcript, preferred)
        self.assertEqual(selection, "preferred")

    def test_select_transcript_falls_back_to_any_available_language(self):
        japanese = FakeTranscript("ja", "Japanese", is_generated=True)
        transcript, selection = fetch_transcript._select_transcript(FakeTranscriptList([japanese]))
        self.assertIs(transcript, japanese)
        self.assertEqual(selection, "fallback-any-language")

    def test_object_snippets_render_without_dict_get_error(self):
        fetched = FetchedTranscript([Snippet("hello\nworld", 1.2, 3.4)])
        snippets = fetch_transcript._snippet_list(fetched)
        markdown = fetch_transcript.transcript_to_markdown("https://youtu.be/abc12345678", "abc12345678", "en", fetched)

        self.assertEqual(snippets, [{"text": "hello\nworld", "start": 1.2, "duration": 3.4}])
        self.assertIn("[00:01]", markdown)
        self.assertIn("hello world", markdown)

    def test_timestamp_display_matches_link_seconds(self):
        markdown = fetch_transcript.transcript_to_markdown(
            "https://www.youtube.com/watch?v=abc12345678",
            "abc12345678",
            "en",
            [{"text": "near a minute", "start": 59.6, "duration": 1}],
        )

        self.assertIn("[00:59](https://www.youtube.com/watch?v=abc12345678&t=59s)", markdown)

    def test_main_uses_canonical_video_url_in_markdown(self):
        original_fetch = fetch_transcript.fetch_transcript
        original_argv = sys.argv

        try:
            fetch_transcript.fetch_transcript = lambda *args, **kwargs: fetch_transcript.TranscriptResult(
                language_code="en",
                language_name="English",
                is_generated=False,
                selection="test",
                transcript=[{"text": "hello", "start": 0, "duration": 1}],
            )
            with tempfile.TemporaryDirectory() as tmp_dir:
                out_dir = Path(tmp_dir)
                sys.argv = ["fetch_transcript.py", "abc12345678", "--out-dir", str(out_dir)]
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(fetch_transcript.main(), 0)
                markdown = (out_dir / "abc12345678.transcript.en.md").read_text(encoding="utf-8")
                self.assertIn("- Source: https://www.youtube.com/watch?v=abc12345678", markdown)
        finally:
            fetch_transcript.fetch_transcript = original_fetch
            sys.argv = original_argv

    def test_extracts_player_response_json_with_nested_braces(self):
        page = 'x ytInitialPlayerResponse = {"a":{"b":"} still string"},"c":1}; y'
        self.assertEqual(fetch_transcript._json_value_after_marker(page, "ytInitialPlayerResponse")["a"]["b"], "} still string")

    def test_extracts_innertube_api_key(self):
        page = 'x "INNERTUBE_API_KEY": "AIzaSyExample_123-abc" y'
        self.assertEqual(fetch_transcript._extract_innertube_api_key(page), "AIzaSyExample_123-abc")

    def test_select_caption_track_uses_preferred_languages_then_fallback(self):
        tracks = [
            {"languageCode": "ja", "name": {"simpleText": "Japanese"}},
            {"languageCode": "en", "name": {"simpleText": "English"}},
        ]
        track, selection = fetch_transcript._select_caption_track(tracks)
        self.assertEqual(track["languageCode"], "en")
        self.assertEqual(selection, "preferred")

        track, selection = fetch_transcript._select_caption_track(tracks[:1])
        self.assertEqual(track["languageCode"], "ja")
        self.assertEqual(selection, "fallback-any-language")

    def test_parse_caption_payload_supports_xml_and_json3(self):
        xml_payload = '<transcript><text start="1.2" dur="3.4">hello &amp;amp; world</text></transcript>'
        json_payload = '{"events":[{"tStartMs":1200,"dDurationMs":3400,"segs":[{"utf8":"hello "},{"utf8":"world"}]}]}'

        self.assertEqual(
            fetch_transcript._parse_caption_payload(xml_payload),
            [{"text": "hello & world", "start": 1.2, "duration": 3.4}],
        )
        self.assertEqual(
            fetch_transcript._parse_caption_payload(json_payload),
            [{"text": "hello world", "start": 1.2, "duration": 3.4}],
        )

    def test_normalizes_youtube_transcript_io_object_track_response(self):
        payload = [
            {
                "id": "abc12345678",
                "title": "Example",
                "tracks": [
                    {
                        "languageCode": "en",
                        "languageName": "English",
                        "isGenerated": True,
                        "transcript": [
                            {"text": "hello", "start": 1.2, "duration": 3.4},
                            {"text": "world", "startMs": 5600, "durationMs": 1200},
                        ],
                    }
                ],
            }
        ]

        result = fetch_transcript._normalize_youtube_transcript_io_result(payload, "abc12345678")

        self.assertEqual(result.language_code, "en")
        self.assertEqual(result.language_name, "English")
        self.assertTrue(result.is_generated)
        self.assertEqual(result.selection, "youtube-transcript-io-preferred")
        self.assertEqual(
            result.transcript,
            [
                {"text": "hello", "start": 1.2, "duration": 3.4},
                {"text": "world", "start": 5.6, "duration": 1.2},
            ],
        )

    def test_normalizes_youtube_transcript_io_segment_array_track_response(self):
        payload = {
            "data": '[{"id":"abc12345678","tracks":[[{"text":"hello\\nworld","start":"00:01","duration":"2"}]]}]'
        }

        result = fetch_transcript._normalize_youtube_transcript_io_result(payload, "abc12345678")

        self.assertEqual(result.language_code, "unknown")
        self.assertEqual(result.selection, "youtube-transcript-io-fallback-any-language")
        self.assertEqual(result.transcript, [{"text": "hello world", "start": 1.0, "duration": 2.0}])

    def test_fetch_transcript_auto_uses_free_api_first_then_falls_back_to_io_when_token_is_configured(self):
        original_io = fetch_transcript.fetch_transcript_from_youtube_transcript_io
        original_api = fetch_transcript.fetch_transcript_with_api
        original_page = fetch_transcript.fetch_transcript_from_page

        calls = []

        def mock_api(*args, **kwargs):
            calls.append(("api", ""))
            raise fetch_transcript.TranscriptFetchError("api error")

        def mock_page(*args, **kwargs):
            calls.append(("page", ""))
            raise fetch_transcript.TranscriptFetchError("page error")

        try:
            fetch_transcript.fetch_transcript_from_youtube_transcript_io = lambda *args, **kwargs: calls.append(
                ("io", kwargs["api_token"])
            ) or fetch_transcript.TranscriptResult(
                language_code="en",
                language_name="English",
                is_generated=None,
                selection="youtube-transcript-io-test",
                transcript=[{"text": "hello", "start": 0, "duration": 1}],
            )
            fetch_transcript.fetch_transcript_with_api = mock_api
            fetch_transcript.fetch_transcript_from_page = mock_page

            result = fetch_transcript.fetch_transcript(
                "abc12345678",
                method="auto",
                youtube_transcript_io_token="secret",
            )

            self.assertEqual(result.selection, "youtube-transcript-io-test")
            self.assertEqual(calls, [("api", ""), ("page", ""), ("io", "secret")])
        finally:
            fetch_transcript.fetch_transcript_from_youtube_transcript_io = original_io
            fetch_transcript.fetch_transcript_with_api = original_api
            fetch_transcript.fetch_transcript_from_page = original_page

    def test_forced_youtube_transcript_io_requires_token(self):
        original_token = os.environ.pop(fetch_transcript.YOUTUBE_TRANSCRIPT_IO_TOKEN_ENV, None)
        try:
            with self.assertRaises(SystemExit) as exc:
                fetch_transcript.fetch_transcript("abc12345678", method="io", youtube_transcript_io_token="")
        finally:
            if original_token is not None:
                os.environ[fetch_transcript.YOUTUBE_TRANSCRIPT_IO_TOKEN_ENV] = original_token

        self.assertIn("Missing youtube-transcript.io API token", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
