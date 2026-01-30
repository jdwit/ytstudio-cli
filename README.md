# ytcli

CLI tool to manage and analyze your YouTube channel.

## Installation

```bash
pip install -e .
```

## Setup

1. Create a [Google Cloud project](https://console.cloud.google.com/)
2. Enable **YouTube Data API v3** and **YouTube Analytics API**
3. Create OAuth credentials (Desktop app) and download JSON
4. Configure ytcli:

```bash
yt init --client-secrets /path/to/client_secrets.json
yt login
```

## Usage

```bash
# Authentication
yt status                    # show current auth status
yt login                     # authenticate via browser
yt auth logout               # remove credentials

# Videos
yt videos list               # list videos (default: 20)
yt videos list -n 50         # limit results
yt videos list -o json       # output as json
yt videos get VIDEO_ID       # get video details
yt videos update VIDEO_ID --title "New Title"
yt videos bulk-update -s "old" -r "new" --field title --dry-run

# Analytics
yt analytics retention VIDEO_ID
yt analytics traffic VIDEO_ID --days 28
yt analytics overview
```

## Configuration

Credentials stored in `~/.config/ytcli/`.

## License

MIT
