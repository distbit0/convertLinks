# lineate

Lineate converts X, Discord, Telegram, Youtube or Apple podcast conversations into a linear article or summary for easier reading.

## What it does
- Paste a link (or any text containing links) and get back cleaned/converted URLs.
- For supported sources, it fetches content/transcripts and writes them to a private GitHub Gist, returning the gist URL.
- By default it opens the processed URL(s) in your browser.

Supported conversions include:
- YouTube: fetch transcript and write gist with timestamped links.
- Twitter/X: fetch tweet + thread via internal GraphQL and write gist.
- Discord & Telegram: fetch message history from a given message and write gist.
- GitBook/Discourse: fetch markdown and write gist.
- Medium/Substack/Articles: extract the main article content and write gist.
- MP3/MP4/Rumble/Streameth/SoundCloud/Apple Podcasts: download audio/video, transcribe with Whisper, write gist.

URL requirements (what to paste):
- YouTube: video URL
- Twitter/X: tweet URL
- Discord: message URL
- Telegram: message URL
- Apple Podcasts: podcast/episode URL
- SoundCloud: track URL
- Rumble: video URL
- Streameth: video URL
- MP3/MP4: direct file URL
- GitBook/Discourse: page URL
- Medium/Substack/Articles: article URL

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
Put these in this repo’s `.env` 

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

How to get each key (links + minimal steps):
- `gh_api_key`: create a GitHub personal access token (fine-grained or classic). For fine-grained, grant User permissions → Gists (read/write). Docs: [Creating a personal access token](https://docs.github.com/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token), [Gists permission scope](https://docs.github.com/en/rest/overview/permissions-required-for-fine-grained-personal-access-tokens#user-permissions-for-gists).
- `OPENAI_API_KEY`: create/view your key in the OpenAI API keys page. Doc: [Where do I find my OpenAI API key?](https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key).
- Telegram (`TELEGRAM_API_ID`, `TELEGRAM_API_HASH`): create an app on Telegram’s developer portal and copy the values from API development tools. Doc: [Creating your Telegram Application](https://core.telegram.org/api/obtaining_api_id).
- Discord (`DISCORD_AUTH_TOKEN`) — **unofficial**: extract your user token from the browser’s developer tools (Network → request headers → `Authorization`). Doc: [discordpy-self “Authenticating”](https://discordpy-self.readthedocs.io/en/latest/authenticating.html).
- Twitter/X (`TWITTER_BEARER_TOKEN`, `TWITTER_CT0_TOKEN`, `TWITTER_COOKIE`) — **unofficial**: use browser devtools on x.com to copy cookies (`auth_token`, `ct0`) and the request `Authorization: Bearer ...` header. Docs: [Export X cookies (auth_token, ct0)](https://readybot.io/help/how-to/find-x-twitter-authentication-token), [Extract Bearer token from request headers](https://gist.github.com/jonathansampson/2814580886e5a5e2d0aaecd32794d53c).

## System dependencies
- `uv` – Python package manager used to sync/install deps.
- `ffmpeg` – required by `pydub` and `yt-dlp` for audio conversion.
- `yt-dlp` – required for some sources (e.g., Rumble).
- Clipboard helper for `pyperclip`:
  - Linux (X11): `xclip` or `xsel` (or `wl-clipboard` on Wayland)
  - macOS: `pbcopy`/`pbpaste` (built-in)

Install (CLI dependencies):
- macOS (Homebrew):
  - `brew install ffmpeg yt-dlp uv`
- Linux (Fedora):
  - `sudo dnf install ffmpeg yt-dlp uv`

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
