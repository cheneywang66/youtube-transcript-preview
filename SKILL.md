---
name: youtube-transcript-preview
description: Fetch, translate, and summarize timestamped YouTube transcripts so a user can quickly decide whether a long YouTube video is worth watching. Use when the user provides a YouTube link and asks to preview, judge, analyze, summarize, inspect, skim, or create a timestamped Chinese note from a long video, especially when they want local Markdown files with transcript and chapter-style summaries.
---

# YouTube Transcript Preview

## Workflow

1. Confirm the Markdown output directory before fetching any transcript.
   - If the user did not already provide a directory, pause and ask this exact question in Chinese:

     `请告诉我这些 Markdown 文件要保存到哪个目录？如果没有指定目录，我会默认保存到当前工作区下的 youtube-transcript-preview/ 文件夹。`

   - If the user has no preference, create and use `youtube-transcript-preview/` under the current workspace.
   - Use the same chosen directory for the raw transcript, translated transcript, and summary.
   - Do not fetch subtitles before this directory is decided.
   - Do not write to a random home directory.

2. Fetch the timestamped transcript with `scripts/fetch_transcript.py`.
   - Prefer Chinese subtitles in this order: `zh-Hans`, `zh-CN`, `zh`, `zh-Hant`, `zh-TW`.
   - If Chinese is unavailable, fetch English subtitles in this order: `en`, `en-US`, `en-GB`.
   - Save the raw timestamped transcript as Markdown.
   - Include the video URL, video ID, transcript language, and every segment timestamp.

3. If the fetched transcript is English, translate it into Chinese and save a second Markdown file.
   - Use the currently executing agent/model to read and translate the Markdown transcript directly.
   - Do not install or call external machine-translation packages or services such as `deep-translator`, `googletrans`, Google Translate, DeepL, or browser-based translation.
   - Preserve all timestamps and segment ordering.
   - Translate meaning naturally; do not summarize during translation.
   - Keep technical terms and named entities accurate.

4. Analyze the Chinese transcript file.
   - Use the Chinese transcript if available; otherwise use the translated Chinese file.
   - Produce a chapter-style Markdown summary with timestamps.
   - Group content into coherent sections based on topic shifts, not fixed time intervals.
   - For each chapter include:
     - Start timestamp linked to the YouTube URL with `&t=<seconds>s`
     - A concise Chinese title
     - Key claims, examples, methods, or arguments
     - Why this section may or may not be worth watching

5. End by telling the user the paths of:
   - Raw transcript Markdown
   - Translated Chinese transcript Markdown, if created
   - Timestamped chapter summary Markdown

## Fetching Transcripts

Run:

```bash
python3 /path/to/youtube-transcript-preview/scripts/fetch_transcript.py "YOUTUBE_URL" --out-dir "OUTPUT_DIR"
```

The script prints JSON containing the generated Markdown path, detected language, and video metadata. Use that JSON to decide whether translation is required.

If `youtube-transcript-api` is not installed, install it only after getting user approval for network access. Prefer:

```bash
python3 -m pip install youtube-transcript-api
```

## Translation Policy

When translation is required, the executing model must perform the translation itself.

Read the transcript Markdown in chunks if it is too large for one pass. For each chunk:

- Preserve every timestamp link exactly.
- Translate only the subtitle text after each timestamp.
- Keep the original line order and Markdown structure.
- Append translated chunks into `<video_id>.transcript.zh-translated.md`.

Do not solve translation by installing packages, calling web translation APIs, opening browser translators, or running code that delegates the translation to another translation service. The only allowed script in this skill is for fetching transcripts, not translating or summarizing them.

## Output Names

Use stable, readable filenames:

- `<video_id>.transcript.<lang>.md`
- `<video_id>.transcript.zh-translated.md`
- `<video_id>.summary.zh.md`

Keep all files in the chosen output directory.

## Summary Style

Write for fast human triage. The summary should help the user decide whether to watch the video, not replace the video entirely.

Prefer:

- Dense but scannable sections
- Specific claims over vague topic labels
- Time links that jump directly to useful moments
- A short final verdict: `值得看`, `可跳读`, or `不建议花完整时间`

Avoid:

- Generic video-review language
- Inventing chapter boundaries that are not supported by the transcript
- Removing timestamps during translation or summarization
