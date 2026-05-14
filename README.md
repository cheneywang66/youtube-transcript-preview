# YouTube Transcript Preview

English | [中文](README.zh-CN.md)

Fetch and summarize timestamped YouTube transcripts with a free YouTube subtitle retrieval tool, so you can quickly decide whether a long video is worth watching. Retrieval depends on the current network environment, YouTube availability, and whether the video exposes captions; this project does not use a paid transcript API and cannot guarantee every URL will work.

Philosophy: **Triage information at the speed of thought.** Don't waste 30 minutes on a video that could have been summarized in 30 seconds.

## What You Get
- **Raw Transcript**: The full timestamped transcript in its original language.
- **Chinese Preview Summary**: A structured, chapter-style digest grouped by topic, not just time.
- **Smart Links**: Clickable timestamps that jump directly to the relevant moment on YouTube.
- **Watchability Verdict**: A final verdict on whether to `Watch`, `Skim`, or `Skip`.

## Quick Start
1. Install the core dependency:
   ```bash
   pip install youtube-transcript-api
   ```
2. Paste a YouTube URL and ask your agent to "summarize this video" or "preview this YouTube link".
3. Unless you provide a directory, the agent saves files to `youtube-transcript-preview/` under the current workspace; if you explicitly ask to choose or confirm the directory first, it will ask before fetching.

> Note: transcript retrieval uses a free toolchain. Success depends on your network, IP, regional access, and changes to YouTube pages or caption endpoints. If the current environment cannot reach YouTube or the caption route is blocked, retry from a different network environment.

## How to Use
You can trigger this skill conversationally. Simply tell your agent:
- "Summary of this video: `[URL]`"
- "Is this video worth watching? `[URL]`"
- "Extract the transcript and create a Chinese note for this: `[URL]`"

The agent handles the rest:
- **Directory selection**: Uses the default output directory unless you provide one or ask to confirm first.
- **Fetching**: Runs the local script to pull transcript data.
- **Analysis**: Reads the raw transcript directly, even when it is not Chinese, and generates a Chinese summary.

## Output Files
All results are saved as Markdown in your chosen directory:
- `<video_id>.transcript.<lang>.md` — Original transcript
- `<video_id>.summary.zh.md` — The final chapter-style summary

## How It Works
1. **Free Subtitle Retrieval**: A Python script (`scripts/fetch_transcript.py`) uses the free `youtube-transcript-api` first, then falls back to caption tracks exposed on the YouTube watch page when the API route is blocked. It prefers Chinese, then English, and falls back to any available original transcript.
2. **On-the-fly Processing**: To keep previews fast and token-efficient, non-Chinese transcripts are summarized directly in Chinese instead of being fully translated first.
3. **Local-First**: All data stays in your workspace. No external database or cloud storage is used.
4. **Network-Dependent**: The current environment must be able to access YouTube and its caption data. Retrieval may fail when the network is blocked, an IP is rate-limited, regional access is restricted, or the video has no captions.

## Requirements
- **Python 3.8+**
- **youtube-transcript-api**
- **AI Agent** (e.g., Antigravity, Claude Code)

## License
MIT
