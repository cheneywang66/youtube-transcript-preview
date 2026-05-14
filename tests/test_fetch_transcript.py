import sys
import unittest
from pathlib import Path

from youtube_transcript_api._errors import NoTranscriptFound


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_transcript  # noqa: E402


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
        raise NoTranscriptFound(self.video_id, language_codes, self)


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


if __name__ == "__main__":
    unittest.main()
