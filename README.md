# lineate

Lineate turns links (or clipboard text) into cleaner, more readable outputs, then optionally opens the result in your browser.

## What it does (user perspective)
- Paste a link (or any text containing links) and get back cleaned/converted URLs.
- For supported sources, it fetches content/transcripts and writes them to a private GitHub Gist, returning the gist URL.
- By default it opens the processed URL(s) in your browser.

Supported conversions include:
- YouTube: fetch transcript and write gist with timestamped links.
- Twitter/X: fetch tweet + thread via internal GraphQL and write gist.
- Discord & Telegram: fetch message history from a given message and write gist.
- GitBook/Discourse: fetch markdown and write gist.
- MP3/MP4/Rumble/Streameth/SoundCloud/Apple Podcasts: download audio/video, transcribe with Whisper, write gist.

## Quick start
1) Install Python deps (managed via `pyproject.toml`):
   - `uv sync`
2) Ensure external tools are installed (see below).
3) Fill in `.env` with required keys.
4) Run:
   - `uv run --env-file .env -m lineate "https://..."`
   - or just run with no args to use the clipboard.

## Usage
```bash
uv run --env-file .env -m lineate [text-or-url]
```
Options:
- `--force-no-convert`   Skip conversion for all URLs.
- `--summarise`    Summarize markdown before writing gists.

Hidden behaviors:
- Add `###` in a URL to force refresh even if a gist already exists.

## Environment variables (.env)
Put these in this repo’s `.env` (loaded via `python-dotenv`):

Required for core functionality:
- `gh_api_key` – GitHub personal access token with Gist scope (used by `writeGist`).

Required for audio/video transcription and summarisation:
- `OPENAI_API_KEY` – used for Whisper transcription and GPT summarization.

Required for specific sources:
- Discord: `DISCORD_AUTH_TOKEN`
- Telegram: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION_NAME`
- Twitter/X: `TWITTER_BEARER_TOKEN`, `TWITTER_CT0_TOKEN`, `TWITTER_COOKIE`
  - Optional: `TWITTER_USER_AGENT`, `TWITTER_XCLIENTTXID`, `TWITTER_XCLIENTUUID`

Notes:
- Telethon will create a `.session` file named after `TELEGRAM_SESSION_NAME` in the repo.
- Twitter/X credentials need to be refreshed if the session expires.

## External tools (system dependencies)
- `ffmpeg` – required by `pydub` and `yt-dlp` for audio conversion.
- Clipboard helper for `pyperclip`:
  - Linux (X11): `xclip` or `xsel` (or `wl-clipboard` on Wayland)
  - macOS: `pbcopy`/`pbpaste` (built-in)

## Python dependencies used by lineate
Installed via `uv sync` from `pyproject.toml`. Key runtime packages:
- `requests`, `loguru`, `python-dotenv`, `pyperclip`
- `openai` (Whisper transcription)
- `pydub` (audio slicing)
- `youtube-transcript-api`, `bs4`
- `telethon` (Telegram)
- `yt-dlp` (Rumble)
- `soundcloud-lib`
- `python-dateutil` (Discord timestamps)
