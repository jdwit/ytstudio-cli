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

Credentials stored in `~/.config/ytstudio/`.

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
