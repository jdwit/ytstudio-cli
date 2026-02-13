# YT Studio CLI

[![CI](https://github.com/jdwit/ytstudio/actions/workflows/ci.yml/badge.svg)](https://github.com/jdwit/ytstudio/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ytstudio-cli)](https://pypi.org/project/ytstudio-cli/)
[![Python](https://img.shields.io/pypi/pyversions/ytstudio-cli)](https://pypi.org/project/ytstudio-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Manage and analyze your YouTube channel from the terminal. Ideal for automation and AI workflows.

![demo](demo.gif)

## Motivation

I built this because I needed to bulk update video titles for a YouTube channel I manage with 300+ videos. YouTube 
Studio does not support bulk search-replace operations, which made it a tedious manual process. This tool uses the 
YouTube Data API to perform bulk operations on video metadata. Furthermore, it provides features for analytics and 
comment moderation, all accesible from the command line.

## Installation

I recommend the excellent [uv](https://uv.io/) tool for installation:

```bash
uv tool install ytstudio-cli
```

## Setup

1. Create a [Google Cloud project](https://console.cloud.google.com/)
2. Enable **YouTube Data API v3** and **YouTube Analytics API**
3. Configure OAuth consent screen:
   - Go to **APIs & Services** → **OAuth consent screen**
   - Select **External** and create
   - Fill in app name and your email
   - Skip scopes, then add yourself as a test user
   - Leave the app in "Testing" mode (no verification needed)
4. Create OAuth credentials:
   - Go to **APIs & Services** → **Credentials**
   - Click **Create Credentials** → **OAuth client ID**
   - Select **Desktop app** as application type
   - Download the JSON file
5. Configure ytstudio:

```bash
ytstudio init --client-secrets path/to/client_secret_<id>.json
ytstudio login
```

Credentials stored in `~/.config/ytstudio/`.

## Disclaimer

This project is not affiliated with or endorsed by Google. YouTube and YouTube Studio are trademarks of Google.
All channel data is accessed exclusively through the official [YouTube Data API](https://developers.google.com/youtube/v3) and [YouTube Analytics API](https://developers.google.com/youtube/analytics).