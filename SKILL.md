---
name: youtube-transcript-preview
description: "Fetch YouTube transcripts with a free subtitle retrieval tool and create local Markdown files: one raw timestamped transcript and one timestamped Chinese preview summary. Retrieval depends on the current network environment and whether YouTube exposes captions for the video. Use when the user provides a YouTube link and asks to save, preview, judge, analyze, summarize, inspect, skim, or create notes from a video, especially when they want chapter-style Chinese notes with YouTube timestamp links."
---

# YouTube Transcript Preview

## Workflow

1. Decide the Markdown output directory before fetching any transcript.
   - If the user already provided a directory, use it.
   - If the user did not provide a directory, pause before fetching and ask in Chinese:

     `请告诉我这些 Markdown 文件要保存到哪个目录？如果没有指定目录，我会默认保存到当前工作区下的 youtube-transcript-preview/ 文件夹。`

   - If the user replies with a directory path, use that directory.
   - If the user does not choose a directory, replies that the default is OK, or gives no specific path, create and use `youtube-transcript-preview/` under the current workspace.
   - Use the same chosen directory for the raw transcript and summary.
   - Do not fetch subtitles before this directory is decided.
   - Do not write to a random home directory.

2. Fetch the timestamped transcript with `scripts/fetch_transcript.py`.
   - Prefer Chinese subtitles in this order: `zh-Hans`, `zh-CN`, `zh`, `zh-Hant`, `zh-TW`.
   - If Chinese is unavailable, fetch English subtitles in this order: `en`, `en-US`, `en-GB`.
   - If neither Chinese nor English is available, fetch the first available original transcript rather than failing.
   - The script defaults to `--method auto`: it tries `youtube-transcript-api` first, then falls back to reading `captionTracks` from the YouTube watch page.
   - Save the raw timestamped transcript as Markdown.
   - Include the video URL, video ID, transcript language, and every segment timestamp.

3. Analyze the raw transcript and produce a Chinese preview summary.
   - Do not translate the full transcript into a separate Chinese transcript file.
   - If the raw transcript is not Chinese, read it directly and summarize its meaning in Chinese.
   - Preserve cited timestamps in the summary, but do not preserve every subtitle line.
   - Write a chapter-style Markdown summary with timestamps to `<video_id>.summary.zh.md`.
   - Group content into coherent sections based on topic shifts, not fixed time intervals.
   - For each chapter include:
     - Start timestamp linked to the YouTube URL with `&t=<seconds>s`
     - A concise Chinese title
     - Key claims, examples, methods, or arguments
     - Why this section may or may not be worth watching

4. End by telling the user the paths of:
   - Raw transcript Markdown
   - Timestamped chapter summary Markdown

## Fetching Transcripts

This skill uses a free YouTube subtitle retrieval toolchain. It does not rely on a paid transcript API. Fetching still depends on the current network environment, YouTube availability, IP or regional access, and whether the target video exposes captions.

Run:

```bash
python3 scripts/fetch_transcript.py "YOUTUBE_URL" --out-dir "OUTPUT_DIR"
```

Run the command from the skill directory, or resolve `scripts/fetch_transcript.py` relative to this `SKILL.md`.

The script prints JSON containing the generated Markdown path, detected language, and video metadata. Use that JSON to decide whether the summary should read a Chinese or non-Chinese raw transcript.

If the `youtube-transcript-api` route is blocked for the current network/IP, the default `--method auto` mode will try the page-based `captionTracks` fallback. To force one route during debugging, pass `--method api` or `--method page`.

If both routes fail because the current network cannot reach YouTube, the IP is blocked or rate-limited, regional access is restricted, or the video has no available captions, explain that the free subtitle retrieval depends on network conditions and suggest retrying from a different network environment.

If `youtube-transcript-api` or `requests` is not installed, install missing dependencies only after getting user approval for network access. Prefer:

```bash
python3 -m pip install youtube-transcript-api
```

If fetching fails because network access is blocked by the current environment, request permission for network access and retry the same command.

## Non-Chinese Transcript Policy

Do not create a full Chinese translation when the fetched transcript is not Chinese.

Instead:

- Read the raw transcript in chunks if it is too large for one pass.
- Extract the important claims, examples, arguments, and topic shifts.
- Write the chapter-style summary in Chinese.
- Quote or preserve only the timestamps needed for useful navigation.
- Keep named entities and technical terms accurate.

The only generated Markdown besides the raw transcript should be the Chinese summary.

## Output Names

Use stable, readable filenames:

- `<video_id>.transcript.<lang>.md`
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
- Translating the full transcript when a summary is enough
- Removing useful timestamps from the summary
