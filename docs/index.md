# YT Studio CLI

Manage and analyze your YouTube channel from the terminal. Designed for
humans and AI agents.

## What it is

A small CLI on top of the official
[YouTube Data API](https://developers.google.com/youtube/v3) and
[YouTube Analytics API](https://developers.google.com/youtube/analytics) that
allows for bulk video updates and uploads, scripted analytics queries,
comment moderation, live broadcast control, and bulk playlist operations.

## Why it exists

Managing a YouTube channel at scale feels like click-ops: the web UI has no
advanced features for bulk updates, and things become tedious very fast.
ytstudio gives you a programmable surface to automate administration tasks
and plug your channel into AI agent workflows.

## Highlights

- **Multiple channels** in a single install, with
  per-profile credential storage. See [Multi-channel profiles](profiles.md).
- **Bulk video updates** with search-and-replace on
  titles or descriptions, plus per-video title/description/tag edits. See
  [Bulk video updates](videos.md).
- **Batch upload** from a directory of YAML
  sidecars with resumable, quota-aware behaviour. See
  [Upload a batch from sidecars](videos.md#upload-a-batch-from-sidecars).
- **Scripted analytics** with table or JSON output.
  See [Analytics](analytics.md).
- **Live broadcast control** for the full lifecycle:
  schedule, start (testing or live), update, stop, with stream-key handling.
  See [Live broadcasts](livestreams.md).
- **Comment moderation** at the CLI:
  approve, reject, or ban in bulk. See [Comments](comments.md).
- **Bulk playlist operations** including adding a search
  query's worth of videos at once and reordering by views. See
  [Playlists](playlists.md).
- **OAuth credentials live owner-only
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

!!! warning
    This is **not** an officially supported Google or YouTube product.

YouTube and YouTube Studio are trademarks of Google. All channel data is
accessed exclusively through the official YouTube Data and Analytics APIs.
