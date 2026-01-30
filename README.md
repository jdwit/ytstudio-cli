# ytcli

CLI tool to manage and analyze your YouTube channel.

## Installation

```bash
uv pip install -e .
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

## Commands

### Authentication

```bash
yt status              # show auth status
yt login               # authenticate via browser
yt auth logout         # clear credentials
```

### Videos

```bash
yt videos list                              # list videos
yt videos list -n 50 --sort views           # sort by views/likes/date
yt videos get VIDEO_ID                      # video details
yt videos update VIDEO_ID --title "New"     # update metadata
yt videos update VIDEO_ID --tags "a,b,c"
```

### Bulk Operations

```bash
# search-replace (dry-run by default)
yt videos bulk-update -s "old" -r "new" --field title
yt videos bulk-update -s "old" -r "new" --field title --execute
yt videos bulk-update -s "^prefix" -r "" --regex --execute
```

### Analytics

```bash
yt analytics overview --days 28            # channel overview
yt analytics video VIDEO_ID                # video analytics
yt analytics top --days 28 --limit 10      # top performers
yt analytics traffic VIDEO_ID              # traffic sources
```

### Comments

```bash
yt comments list VIDEO_ID                  # list comments
yt comments summary VIDEO_ID               # sentiment analysis
```

### SEO

```bash
yt seo check VIDEO_ID                      # check video SEO
yt seo audit --limit 50                    # audit channel
```

### Export

```bash
yt export videos data.csv                  # export to CSV
yt export videos data.json -f json         # export to JSON
yt export comments VIDEO_ID comments.json  # export comments
yt export report report.json               # full channel report
```

### Output Formats

Most commands support `--output table|json|csv`.

## Configuration

Credentials stored in `~/.config/ytcli/`.

## Development

```bash
uv pip install -e ".[dev]"
pytest -v
```
