# YouTube Transcript Preview (视频字幕预览)

[English](README.md) | 中文

获取并总结带有时间戳的 YouTube 字幕，助你快速判断长视频是否值得观看。默认流程会先尝试免费字幕路径；如果免费路径失败且你提供了 `youtube-transcript.io` API token，抓取器会回退到它的托管 REST API。抓取结果仍依赖服务商、当前网络环境、YouTube 可访问性以及视频本身是否开放字幕。

核心理念：**以思考的速度筛选信息。** 不要把 30 分钟浪费在一个本可以用 30 秒总结完的视频上。

## 你将获得
- **原始字幕**：原始语言的完整带时间戳字幕。
- **中文预览摘要**：按主题（而非固定时间间隔）分组的结构化章节摘要。
- **智能链接**：可点击的时间戳链接，直接跳转到 YouTube 对应时刻。
- **观感评价**：最终给出 `值得看`、`可跳读` 或 `不建议` 的专业评价。

## 快速开始
1. 向 AI 助手发送一个 YouTube 链接，并要求“总结这个视频”或“预览这个链接”。
2. 助手会先尝试免费字幕路径，包括 `youtube-transcript-api` 和 YouTube 页面 `captionTracks` 兜底。
3. 如果你希望免费路径失败后回退到 `youtube-transcript.io`，可以提供 token；命令行直接使用时也可以提前设置：
   ```bash
   export YOUTUBE_TRANSCRIPT_IO_API_TOKEN="your-api-token"
   ```
4. 安装脚本依赖：
   ```bash
   pip install requests youtube-transcript-api
   ```
5. 如果你没有指定目录，助手会把文件保存到当前工作区下的 `youtube-transcript-preview/`；如果你明确要求先选择或确认目录，助手会在抓取前询问。

> 注意：`youtube-transcript.io` 需要 API token，并受服务商限流约束。token 只用于本次字幕请求，不应写入生成的 Markdown 或最终回复。

## 使用指南
你可以通过对话直接触发此技能，例如：
- “总结一下这个视频：`[URL]`”
- “这个视频值得看吗？`[URL]`”
- “提取字幕并为我生成一份中文笔记：`[URL]`”

助手将自动完成剩余工作：
- **免费优先**：默认先尝试 `youtube-transcript-api`，再尝试 YouTube 页面 `captionTracks`。
- **托管 API 兜底**：如果免费路径失败且你提供 token，再回退到 `youtube-transcript.io`。
- **确认**：按你的要求确认输出目录；未指定时使用默认目录。
- **获取**：运行本地脚本提取字幕数据。
- **分析**：直接读取原始字幕；即使字幕不是中文，也只生成中文摘要，不逐行翻译全文。

## 输出文件
所有结果均以 Markdown 格式保存：
- `<video_id>.transcript.<lang>.md` — 原始字幕
- `<video_id>.summary.zh.md` — 最终的章节总结

## 工作原理
1. **免费方式获取字幕**：触发 skill 后，脚本默认使用免费的 `youtube-transcript-api` 包和 YouTube 页面 `captionTracks` 获取字幕；优先中文，其次英文，最后尝试抓取任意可用的原始字幕。免费方式可能因为网络/IP 限制、区域访问或视频没有可用字幕而失败。
2. **托管 API 兜底**：如果免费路径失败且配置了 token，Python 脚本 (`scripts/fetch_transcript.py`) 会向 `POST /api/transcripts` 发送视频 ID，并把返回的 transcript tracks 规范化为带时间戳的 Markdown。
3. **可强制托管 API**：如果你明确要求使用 `youtube-transcript.io`，可以通过 `--method io` 强制托管 API。
4. **实时处理**：为了快速预览并节省 token，非中文字幕会被直接用于生成中文摘要，不再先完整翻译。
5. **本地输出**：生成的 Markdown 保存在你的工作区。启用托管 API 时，视频 ID 会发送给 `youtube-transcript.io` 用于检索字幕。
6. **网络依赖**：该工具需要当前环境能够访问配置的服务商和/或 YouTube 字幕数据；网络不可达、地区限制、IP 被临时阻断或视频没有字幕时，抓取可能失败。

## 抓取方式
```bash
python3 scripts/fetch_transcript.py "https://youtu.be/VIDEO_ID" --out-dir ./out
```

- `--method io` 或 `--method youtube-transcript-io`：强制使用托管 API。
- `--youtube-transcript-io-token`：为本次命令传入 token；也可以用 `YOUTUBE_TRANSCRIPT_IO_API_TOKEN` 环境变量。
- `--method auto`：仅在你明确选择使用免费方式获取字幕时使用；配置 token 时会先尝试免费路径，失败后再回退到 `youtube-transcript.io`。免费方式可能失败。
- `--method api`：强制使用 `youtube-transcript-api` 包。
- `--method page`：强制使用 YouTube 页面 `captionTracks` 兜底路径。

## 需求
- **Python 3.8+**
- **requests**（托管 API 和页面兜底使用）
- **youtube-transcript-api**（免费方式获取字幕时使用）
- **AI 助手** (如 Antigravity, Claude Code)

## 开源协议
MIT
