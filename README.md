# YouTube Transcript Preview

English | [中文](README.zh-CN.md)

Fetch and summarize timestamped YouTube transcripts, so you can quickly decide whether a long video is worth watching. The default workflow tries free subtitle routes first; if they fail and you provide a `youtube-transcript.io` API token, the fetcher falls back to its managed REST API. Retrieval still depends on the provider, network environment, YouTube availability, and whether the video exposes captions.

Philosophy: **Triage information at the speed of thought.** Don't waste 30 minutes on a video that could have been summarized in 30 seconds.

## What You Get
- **Raw Transcript**: The full timestamped transcript in its original language.
- **Chinese Preview Summary**: A structured, chapter-style digest grouped by topic, not just time.
- **Smart Links**: Clickable timestamps that jump directly to the relevant moment on YouTube.
- **Watchability Verdict**: A final verdict on whether to `Watch`, `Skim`, or `Skip`.

## Quick Start
1. Paste a YouTube URL and ask your agent to "summarize this video" or "preview this YouTube link".
2. The agent first tries free subtitle routes, including `youtube-transcript-api` and the YouTube page `captionTracks` fallback.
3. If you want `youtube-transcript.io` fallback after free routes fail, provide a token; for direct CLI use, you can set it ahead of time:
   ```bash
   export YOUTUBE_TRANSCRIPT_IO_API_TOKEN="your-api-token"
   ```
4. Install the script dependencies:
   ```bash
   pip install requests youtube-transcript-api
   ```
5. Unless you provide a directory, the agent saves files to `youtube-transcript-preview/` under the current workspace; if you explicitly ask to choose or confirm the directory first, it will ask before fetching.

> Note: `youtube-transcript.io` requires an API token and is rate-limited by the provider. The token is only for the current transcript request and should not be written into generated Markdown or final replies.

## How to Use
You can trigger this skill conversationally. Simply tell your agent:
- "Summary of this video: `[URL]`"
- "Is this video worth watching? `[URL]`"
- "Extract the transcript and create a Chinese note for this: `[URL]`"

The agent handles the rest:
- **Free-first retrieval**: Tries `youtube-transcript-api` first, then the YouTube page `captionTracks` fallback.
- **Managed API fallback**: Falls back to `youtube-transcript.io` when free routes fail and you provide a token.
- **Directory selection**: Uses the default output directory unless you provide one or ask to confirm first.
- **Fetching**: Runs the local script to pull transcript data.
- **Analysis**: Reads the raw transcript directly, even when it is not Chinese, and generates a Chinese summary.

## Output Files
All results are saved as Markdown in your chosen directory:
- `<video_id>.transcript.<lang>.md` — Original transcript
- `<video_id>.summary.zh.md` — The final chapter-style summary

## How It Works
1. **Free Subtitle Retrieval**: The script first uses the free `youtube-transcript-api` package and caption tracks exposed on the YouTube watch page. It prefers Chinese, then English, and then tries any available original transcript. Free retrieval may fail because of network/IP restrictions, regional access, or unavailable captions.
2. **Managed API Fallback**: If free routes fail and a token is configured, the Python script (`scripts/fetch_transcript.py`) sends the video ID to `POST /api/transcripts` and normalizes returned transcript tracks into timestamped Markdown.
3. **Forced Managed API**: If you explicitly want `youtube-transcript.io`, use `--method io` to force the managed API.
4. **On-the-fly Processing**: To keep previews fast and token-efficient, non-Chinese transcripts are summarized directly in Chinese instead of being fully translated first.
5. **Local-First Output**: Generated Markdown stays in your workspace. When the managed API is enabled, the video ID is sent to `youtube-transcript.io` for transcript retrieval.
6. **Network-Dependent**: The current environment must be able to access the configured provider and/or YouTube caption data. Retrieval may fail when the network is blocked, an IP is rate-limited, regional access is restricted, or the video has no captions.

## Fetch Methods
```bash
python3 scripts/fetch_transcript.py "https://youtu.be/VIDEO_ID" --out-dir ./out
```

- `--method io` or `--method youtube-transcript-io` forces the managed API.
- `--youtube-transcript-io-token` passes a token for this command; `YOUTUBE_TRANSCRIPT_IO_API_TOKEN` can also be used.
- `--method auto` is for explicitly chosen free subtitle retrieval; when a token is configured, it tries free retrieval routes first, then falls back to `youtube-transcript.io`. Free retrieval may fail.
- `--method api` forces the `youtube-transcript-api` package.
- `--method page` forces the YouTube page `captionTracks` fallback.

## Requirements
- **Python 3.8+**
- **requests** for the managed API and page fallback
- **youtube-transcript-api** for free subtitle retrieval
- **AI Agent** (e.g., Antigravity, Claude Code)

## License
MIT
