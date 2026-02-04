# ytstudio-cli

[![CI](https://github.com/jdwit/ytstudio-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/jdwit/ytstudio-cli/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/jdwit/ytstudio-cli/branch/main/graph/badge.svg)](https://codecov.io/gh/jdwit/ytstudio-cli)
[![PyPI version](https://badge.fury.io/py/ytstudio-cli.svg)](https://pypi.org/project/ytstudio-cli/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

CLI tool to manage and analyze your YouTube channel from the terminal.

## Installation

```bash
pip install ytstudio-cli
```

Or for development:

```bash
uv pip install -e .
```

## Setup

1. Create a [Google Cloud project](https://console.cloud.google.com/)
2. Enable **YouTube Data API v3** and **YouTube Analytics API**
3. Create OAuth credentials (Desktop app) and download JSON
4. Configure ytstudio-cli:

```bash
ytstudio init --client-secrets /path/to/client_secrets.json
ytstudio login
```

## Commands

### Authentication

```bash
ytstudio status              # show auth status
ytstudio login               # authenticate via browser
ytstudio auth logout         # clear credentials
```

### Videos

```bash
ytstudio videos list                              # list videos
ytstudio videos list -n 50 --sort views           # sort by views/likes/date
ytstudio videos get VIDEO_ID                      # video details
ytstudio videos update VIDEO_ID --title "New"     # update metadata
ytstudio videos update VIDEO_ID --tags "a,b,c"
```

### Bulk Operations

```bash
# search-replace (dry-run by default)
ytstudio videos bulk-update -s "old" -r "new" --field title
ytstudio videos bulk-update -s "old" -r "new" --field title --execute
ytstudio videos bulk-update -s "^prefix" -r "" --regex --execute
```

### Analytics

```bash
ytstudio analytics overview --days 28            # channel overview
ytstudio analytics video VIDEO_ID                # video analytics
ytstudio analytics top --days 28 --limit 10      # top performers
ytstudio analytics traffic VIDEO_ID              # traffic sources
```

### Comments

```bash
ytstudio comments list VIDEO_ID                  # list comments
ytstudio comments summary VIDEO_ID               # sentiment analysis
```

### SEO

```bash
ytstudio seo check VIDEO_ID                      # check video SEO
ytstudio seo audit --limit 50                    # audit channel
```

### Export

```bash
ytstudio export videos data.csv                  # export to CSV
ytstudio export videos data.json -f json         # export to JSON
ytstudio export comments VIDEO_ID comments.json  # export comments
ytstudio export report report.json               # full channel report
```

### Output Formats

Most commands support `--output table|json|csv`.

## Configuration

Credentials stored in `~/.config/ytstudio-cli/`.

## Development

```bash
uv sync --all-extras
uv run pre-commit install
uv run pytest
```

### Demo Mode

For screencasts and testing without credentials:

```bash
YTS_DEMO=1 ytstudio videos list
YTS_DEMO=1 ytstudio analytics overview
```

### Recording Demo GIF

```bash
brew install vhs
vhs demo.tape
```
