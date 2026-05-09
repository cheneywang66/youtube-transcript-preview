# YouTube Transcript Preview

English | [中文](README.zh-CN.md)

Fetch, translate, and summarize timestamped YouTube transcripts so you can quickly decide whether a long video is worth watching.

Philosophy: **Triage information at the speed of thought.** Don't waste 30 minutes on a video that could have been summarized in 30 seconds.

## What You Get
- **Raw Transcript**: The full timestamped transcript in its original language.
- **Natural Translation**: High-quality Chinese translation that preserves all timestamps and technical terms.
- **Chapter Summary**: A structured, chapter-style digest grouped by topic, not just time.
- **Smart Links**: Clickable timestamps that jump directly to the relevant moment on YouTube.
- **Watchability Verdict**: A final verdict on whether to `Watch`, `Skim`, or `Skip`.

## Quick Start
1. Install the core dependency:
   ```bash
   pip install youtube-transcript-api
   ```
2. Paste a YouTube URL and ask your agent to "summarize this video" or "preview this YouTube link".
3. The agent will ask where to save the files (default is `youtube-transcript-preview/`).

## How to Use
You can trigger this skill conversationally. Simply tell your agent:
- "Summary of this video: `[URL]`"
- "Is this video worth watching? `[URL]`"
- "Extract the transcript and create a Chinese note for this: `[URL]`"

The agent handles the rest:
- **Confirmation**: Verifies the output directory.
- **Fetching**: Runs the local script to pull transcript data.
- **Translation**: Translates English transcripts to Chinese in-memory.
- **Analysis**: Groups content into logical chapters and generates the summary.

## Output Files
All results are saved as Markdown in your chosen directory:
- `<video_id>.transcript.<lang>.md` — Original transcript
- `<video_id>.transcript.zh-translated.md` — Translated transcript
- `<video_id>.summary.zh.md` — The final chapter-style summary

## How It Works
1. **Data Retrieval**: A Python script (`scripts/fetch_transcript.py`) uses the YouTube Transcript API to fetch text and timestamps.
2. **On-the-fly Processing**: Unlike tools that use external translation APIs, this skill uses the model's native reasoning to translate and summarize, ensuring better context retention.
3. **Local-First**: All data stays in your workspace. No external database or cloud storage is used.

## Requirements
- **Python 3.8+**
- **youtube-transcript-api**
- **AI Agent** (e.g., Antigravity, Claude Code)

## License
MIT
