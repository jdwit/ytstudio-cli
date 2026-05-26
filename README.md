# YT Studio CLI

[![CI](https://github.com/jdwit/ytstudio/actions/workflows/ci.yml/badge.svg)](https://github.com/jdwit/ytstudio/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ytstudio-cli)](https://pypi.org/project/ytstudio-cli/)
[![Python](https://img.shields.io/pypi/pyversions/ytstudio-cli)](https://pypi.org/project/ytstudio-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Manage and analyze your YouTube channel from the terminal. Ideal for automation and AI workflows.

![demo](demo.gif)

## Motivation

I built this because I needed to bulk update video titles for a YouTube channel I manage with 300+
videos. YouTube Studio does not support bulk search-replace operations, which made it a tedious
manual process. This tool uses the YouTube Data API to perform bulk operations on video metadata.
Furthermore, it provides features for analytics and comment moderation, all accesible from the
command line.

## Installation

I recommend the excellent [uv](https://uv.io/) tool for installation:

```bash
uv tool install ytstudio-cli
```

The CLI is installed as `ytstudio`; `yts` is a short alias for the same entry point.

Full documentation: [https://jdwit.github.io/ytstudio-cli/](https://jdwit.github.io/ytstudio-cli/).

## Setup

1. Create a [Google Cloud project](https://console.cloud.google.com/)
1. Enable **YouTube Data API v3** and **YouTube Analytics API**
1. Configure OAuth consent screen:
   - Go to **APIs & Services** → **OAuth consent screen**
   - Select **External** and create
   - Fill in app name and your email
   - Skip scopes, then add yourself as a test user
   - Leave the app in "Testing" mode (no verification needed)
1. Create OAuth credentials:
   - Go to **APIs & Services** → **Credentials**
   - Click **Create Credentials** → **OAuth client ID**how
   - Select **Desktop app** as application type
   - Download the JSON file
1. Configure ytstudio:

```bash
ytstudio init --client-secrets path/to/client_secret_<id>.json
ytstudio login
```

Credentials stored in `~/.config/ytstudio-cli/`.

### Headless Linux login

If you are logging in from a server without a browser, run:

```bash
ytstudio login --headless
```

The command prints a Google OAuth URL. Open that URL in a browser on any machine and approve
access. The browser will then fail to load a `127.0.0.1` page; this is expected. Copy the full URL
from the browser address bar, paste it back into the terminal, and ytstudio will finish the login.

## Managing multiple channels

If you run more than one YouTube channel, ytstudio stores each login under its own named profile.
Every command (`videos`, `analytics`, `comments`, ...) operates on the active channel.

```bash
ytstudio profile add work       # authenticate a new channel and make it active
ytstudio profile add personal   # add another
ytstudio profile list           # show profiles; the active one is marked with *
ytstudio profile use work       # switch the active profile
ytstudio profile status work    # auth status for one profile (defaults to active)
ytstudio profile remove personal
```

For scripting you can override the active channel per command without switching:

```bash
YTSTUDIO_PROFILE=work ytstudio videos list
```

Credentials live in `~/.config/ytstudio-cli/profiles/<name>/` with owner-only (`600`) permissions.
The shared OAuth client secrets stay at the top level, so `ytstudio init` is only needed once.
A plain `ytstudio login` (no `profile add`) authenticates the active profile, which is `default`
on a fresh setup. Existing single-channel installs are migrated to the `default` profile
automatically on first run.

## Live broadcasts

Manage your YouTube livestream broadcasts from the CLI. This drives YouTube's
`liveBroadcasts` API (scheduling, starting, stopping, updating); the actual
video push to YouTube still goes through your encoder of choice (OBS, etc.).

```bash
ytstudio livestreams list --status upcoming        # what is scheduled
ytstudio livestreams show <broadcast-id>           # details for one broadcast
ytstudio livestreams show <id> --ingest            # also fetch the bound stream's RTMP URL
ytstudio livestreams show <id> --show-key          # reveal the stream key (treat as secret)
ytstudio livestreams schedule \
    --title "Title" --scheduled-start 2026-06-01T19:00:00+02:00   # dry-run
ytstudio livestreams schedule ... --execute        # actually create
ytstudio livestreams start <id>                    # transition to live
ytstudio livestreams start <id> --to testing       # transition to the monitor stream first
ytstudio livestreams stop <id>                     # transition to complete
ytstudio livestreams update <id> --privacy unlisted --no-dvr   # dry-run by default
```

Notes:

- `schedule` and `update` default to a dry-run preview; pass `--execute` to apply.
- `--show-key` on `show` reveals the bound stream key; without it the key is
  redacted. Stream keys are credentials.
- `liveBroadcasts.insert`/`update` are write operations (~50 quota units each);
  see [API quota](#api-quota) below.

## Uploading videos

Bulk-upload videos from a directory. Each video file needs a YAML sidecar with
the same basename describing its metadata.

```bash
yts videos upload ./outbox                    # dry-run preview
yts videos upload ./outbox --execute          # actually upload
yts videos upload ./outbox --execute --max 3  # cap to N uploads (quota budget)
```

Directory layout:

```
outbox/
  holiday.mp4
  holiday.yaml    # required
  holiday.jpg     # optional thumbnail (or .png), max 2 MB
```

Sidecar (`holiday.yaml`):

```yaml
title: Holiday recap 2026
description: |
  Multi-line description.
privacy: private              # private | unlisted | public
publish_at: 2026-06-01T10:00:00+02:00   # optional; forces privacy=private
tags: [travel, vlog]
category_id: "22"             # YouTube category id; default 22 (People & Blogs)
default_language: nl
default_audio_language: nl
made_for_kids: false
```

After a successful upload the tool patches the sidecar with the resulting
`video_id` and `uploaded_at`, so re-running on the same directory is safe; only
sidecars without a `video_id` get uploaded.

Quota: `videos.insert` costs ~1600 quota units, so on the default 10k/day
quota you can upload ~6 videos per day. Use `--max` to cap a run explicitly.

Show what's scheduled for the future:

```bash
yts videos list --scheduled
```

## Development

Clone the repo, sync dev dependencies, and install the pre-commit hook so
`ruff check` and `ruff format` run on every commit (same checks CI runs):

```bash
uv sync --group dev
uv run pre-commit install
```

Run the suite manually with `uv run pytest` and `uv run pre-commit run --all-files`.

## API quota

The YouTube Data API enforces a default quota of 10_000 units per project per day. Most read
operations (listing videos, comments, channel info) cost 1 unit, while write operations like
updating video metadata or moderating comments cost 50 units each. Bulk updates can consume quota
quickly. When exceeded, the API returns a 403 error; quota resets at midnight Pacific Time.

You can request a quota increase via **IAM & Admin** → **Quotas** in the
[Google Cloud Console](https://console.cloud.google.com/). See the
[official quota documentation](https://developers.google.com/youtube/v3/getting-started#quota) for
full details.

## Disclaimer

This project is not affiliated with or endorsed by Google. YouTube and YouTube Studio are trademarks
of Google. All channel data is accessed exclusively through the official
[YouTube Data API](https://developers.google.com/youtube/v3) and
[YouTube Analytics API](https://developers.google.com/youtube/analytics).
