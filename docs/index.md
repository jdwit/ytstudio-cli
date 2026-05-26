# ytstudio

Manage and analyze your YouTube channel from the terminal. Ideal for
automation and AI workflows.

[![CI](https://github.com/jdwit/ytstudio-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/jdwit/ytstudio-cli/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ytstudio-cli)](https://pypi.org/project/ytstudio-cli/)
[![Python](https://img.shields.io/pypi/pyversions/ytstudio-cli)](https://pypi.org/project/ytstudio-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What it is

A small CLI on top of the official
[YouTube Data API](https://developers.google.com/youtube/v3) and
[YouTube Analytics API](https://developers.google.com/youtube/analytics) that
covers what YouTube Studio cannot, or only at painful speed: bulk video
updates, scripted analytics queries, comment moderation, live broadcast
control, and multiple channels from one install.

## Why it exists

YouTube Studio does not let you bulk-rename 300 videos. ytstudio does. It
also gives you a scriptable surface for the rest of the channel: analytics
you can pipe through `jq`, comment moderation you can run in CI, live
broadcasts you can schedule from a one-liner.

## Highlights

- :material-account-multiple: **Multiple channels** in a single install, with
  per-profile credential storage. See [Multi-channel profiles](profiles.md).
- :material-video-outline: **Bulk video updates** with search-and-replace on
  titles, descriptions, and tags. See [Bulk video updates](videos.md).
- :material-chart-line: **Scripted analytics** with table or JSON output.
  See [Analytics](analytics.md).
- :material-broadcast: **Live broadcast control** for the full lifecycle:
  schedule, start (testing or live), update, stop, with stream-key handling.
  See [Live broadcasts](livestreams.md).
- :material-shield-lock-outline: **OAuth credentials live owner-only
  (`0600`)** under `~/.config/ytstudio-cli/`. The `init` step is one-shot.

## Quick start

```bash
uv tool install ytstudio-cli
ytstudio init --client-secrets path/to/client_secret.json
ytstudio login
ytstudio videos list
```

The CLI is installed as `ytstudio`; `yts` is a short alias for the same
entry point.

Continue with [Installation](installation.md) for the full setup or the
[Command reference](reference.md) for every flag.

## Disclaimer

This project is not affiliated with or endorsed by Google. YouTube and
YouTube Studio are trademarks of Google. All channel data is accessed
exclusively through the official YouTube Data and Analytics APIs.
