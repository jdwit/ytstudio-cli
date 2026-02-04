# ytstudio

CLI tool to manage and analyze your YouTube channel.

## Installation

```bash
uv tool install ytstudio
```

## Setup

1. Create a [Google Cloud project](https://console.cloud.google.com/)
2. Enable **YouTube Data API v3** and **YouTube Analytics API**
3. Create OAuth credentials (Desktop app) and download JSON
4. Configure ytstudio:

```bash
ytstudio init --client-secrets path/to/client_secrets.json
ytstudio login
```

## Configuration

Credentials stored in `~/.config/ytstudio/`.
