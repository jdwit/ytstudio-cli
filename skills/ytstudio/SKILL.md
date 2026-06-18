---
name: ytstudio
description: Manage and automate a YouTube channel from the terminal with the ytstudio CLI - list and bulk-edit video metadata (search-replace titles/descriptions/tags), upload videos from YAML sidecars, query channel and per-video analytics, moderate comments, control live broadcasts, and run bulk playlist operations. Use when a task involves administering, scripting, or reporting on a YouTube channel rather than just watching or searching public videos.
license: MIT
metadata:
  project: ytstudio-cli
  repository: https://github.com/jdwit/ytstudio-cli
  keywords:
    - youtube
    - youtube-studio
    - youtube-channel
    - youtube-analytics
---

# ytstudio

`ytstudio` is a command-line tool over the official YouTube Data and Analytics
APIs. It exists to do at scale what YouTube Studio's web UI makes you click
through one item at a time: bulk metadata edits, batch uploads, scripted
analytics, comment moderation, live broadcast control, and playlist operations.

This skill teaches you to drive it. It is harness-agnostic: every instruction is
a shell command.

## Two things to know first

These two rules apply to almost every command and prevent the most common
mistakes:

1. **Ask for JSON.** Read commands print a human table by default. Pass
   `-o json` (alias for `--output json`) to get parseable output. Some commands
   also support `-o csv`. The auth/setup commands (`init`, `login`, `status`)
   have no JSON mode.
2. **Most mutations are dry-run by default.** Commands with `--execute`
   (`videos update/search-replace/upload`, `livestreams schedule/update`, and
   playlist writes) preview what they *would* do and change nothing until you
   re-run the exact command with `--execute`. Always preview first, show the
   user the preview when consequential, then re-run with `--execute`.

Some writes execute immediately because they have no `--execute`: comment
moderation/replies (`comments publish`, `comments reject`, `comments reply`) and
livestream transitions (`livestreams start`, `livestreams stop`). Treat these as
high-risk: confirm intent before running them.

Treat write operations as costly and irreversible-ish: they consume API quota
(see [Quota](#quota-awareness)) and act on a real, public channel.

## Prerequisites

### Install

`ytstudio` is on PyPI and needs Python 3.12+. Prefer an isolated install:

```bash
uv tool install ytstudio-cli      # recommended
# or: pipx install ytstudio-cli
# or: pip install --user ytstudio-cli
```

The CLI installs as `ytstudio`; `yts` is a short alias for the same entry point.
Verify with `ytstudio --version`.

### One-time OAuth setup

The user brings their own Google OAuth client (a "Desktop app" client created in
the Google Cloud Console with the YouTube Data API v3 and YouTube Analytics API
enabled). With the downloaded client-secrets JSON:

```bash
ytstudio init --client-secrets path/to/client_secret.json
ytstudio login                    # opens a browser to authorize
ytstudio status                   # confirms the authenticated channel
```

On a headless box, use `ytstudio login --headless`: it prints a URL to open in
any browser, then you paste the failed `127.0.0.1` redirect URL back in.

If `ytstudio login` fails with `access_denied`:

- Sign in with the Google account that owns the channel.
- If the OAuth app is still in "Testing", add that account under Google Cloud
  Console -> APIs & Services -> OAuth consent screen -> Test users.
- Click through the "Google hasn't verified this app" warning via Advanced ->
  Continue.
- Approve all requested (read-only) scopes; do not close the tab until it
  reports success.

Credentials live owner-only under `~/.config/ytstudio-cli/`. This step is
one-shot per channel; do not re-run it unless auth is actually broken.

If `ytstudio status` reports no authenticated channel, stop and ask the user to
complete OAuth setup; you cannot do the browser consent for them.

### Multiple channels (profiles)

One install can hold several channels, each a named profile. Commands act on the
**active** profile unless overridden:

```bash
ytstudio profile list             # active profile is marked
ytstudio profile use work         # switch active profile
YTSTUDIO_PROFILE=work ytstudio videos list   # override for one command (scripting)
```

Use the `YTSTUDIO_PROFILE=<name>` env override when scripting so you never mutate
the wrong channel by relying on global state.

## Command groups

Below is the minimum to operate each area. For the complete flag surface of any
command, read [references/reference.md](references/reference.md) on demand
rather than guessing - or run `ytstudio <group> <command> --help`.

### videos - the core use case

```bash
ytstudio videos list -n 100 -o json          # recent uploads, parseable
ytstudio videos list --scheduled             # only future-dated publishes
ytstudio videos show <video-id> -o json      # full metadata for one video
ytstudio videos categories                   # category ids assignable on upload

# Single-video edit (dry-run, then --execute)
ytstudio videos update <video-id> --title "New title"
ytstudio videos update <video-id> --tags one,two,three --execute

# Bulk search-replace across the channel (dry-run, then --execute)
ytstudio videos search-replace -s "2024" -r "2025" -f title
ytstudio videos search-replace -s 'season \d' -r 'season X' -f title --regex --execute
```

`search-replace` requires `-s/--search`, `-r/--replace`, and `-f/--field`
(`title` or `description`); `--limit` caps how many matches it acts on (default
10). Preview the dry-run, confirm the match set is what the user intended, then
add `--execute`.

### videos upload - batch upload from YAML sidecars

`ytstudio videos upload <path>` pairs each video file with a sibling YAML
sidecar of the same basename, validates everything, and uploads. Dry-run by
default. See [assets/upload-sidecar.example.yaml](assets/upload-sidecar.example.yaml)
for the sidecar schema (`title`, `description`, `privacy`, `tags`,
`category_id` (required), languages, `made_for_kids`, optional `publish_at`).

```bash
ytstudio videos upload ./outbox               # validate + preview
ytstudio videos upload ./outbox --execute --max 3   # upload, capped for quota
```

Uploads are resumable: after each success the sidecar is patched with `video_id`
and `uploaded_at`, so re-running only retries sidecars that lack a `video_id`.
Use `--max` to bound a run because uploads are quota-heavy (~1600 units each).

### analytics - reporting (read-only)

```bash
ytstudio analytics overview -d 28 -o json     # channel overview, last 28 days
ytstudio analytics video <video-id> -o json   # per-video analytics
ytstudio analytics metrics                     # discoverable metric names
ytstudio analytics dimensions                  # discoverable dimension names

# Custom query straight against the Analytics API reports.query endpoint:
ytstudio analytics query -m views,likes -d day --days 7 -o json
ytstudio analytics query -m views -d country --sort -views -n 10 -o json
ytstudio analytics query -m views -d insightTrafficSourceType -f video==<id> -o json
```

`analytics query` needs `-m/--metrics`; `-d/--dimensions`, `-f/--filter`
(`key==value`, repeatable), `--sort` (prefix `-` for descending), `-n/--limit`,
and date range (`--days` or `-s/-e` start/end) are optional. When unsure which
metric or dimension exists, list them first with `analytics metrics` /
`analytics dimensions` instead of guessing names.

For `-d month` (and `-d week`), the CLI snaps `-s`/`-e` down to the boundary the
YouTube Analytics API requires (first of the month), so `--days` and arbitrary
dates just work. The range is inclusive on both ends, so the end month is the
last month you want, not the month after.

```bash
# 12 months, Jun 2025 through May 2026:
ytstudio analytics query -m views -d month -s 2025-06-01 -e 2026-05-01
```

### comments - moderation

```bash
ytstudio comments list --status held -o json          # the moderation queue
ytstudio comments list -v <video-id> -n 50 -o json
ytstudio comments publish <comment-id> [<comment-id> ...]   # approve held; executes immediately
ytstudio comments reject <comment-id> --ban                 # reject (+ optional ban); executes immediately
ytstudio comments reply <comment-id> -t "Thanks!"           # executes immediately
```

`publish`/`reject` take one or more comment ids and execute immediately (no
`--execute` dry-run). `reply` also posts immediately. Confirm the exact comment
ids/text first. `--ban` on `reject` also bans the author - only use it when the
user explicitly asks to ban.

### livestreams - broadcast lifecycle

```bash
ytstudio livestreams list -s upcoming -o json
ytstudio livestreams show <broadcast-id> --ingest -o json   # ingest URL; key redacted
ytstudio livestreams schedule -t "Title" --scheduled-start 2026-07-01T19:00:00+02:00 --execute
ytstudio livestreams start <broadcast-id> --to testing      # executes immediately; or --to live
ytstudio livestreams stop <broadcast-id>                    # executes immediately
ytstudio livestreams update <broadcast-id> --privacy unlisted --execute
```

`schedule`/`update` are dry-run until `--execute`, but `start`/`stop` execute
immediately. `livestreams show --show-key` reveals the stream key - treat any
such output as a secret and never echo it into logs or chat. `start --to live`
publishes to viewers; prefer `--to testing` unless the user wants to go live
immediately.

### playlists - bulk operations

```bash
ytstudio playlists list -o json
ytstudio playlists items <playlist-id> -o json
ytstudio playlists create -t "Title" --privacy unlisted --execute
ytstudio playlists add <playlist-id> --from-search "topic" -n 20 --execute   # search costs 100 units/call
ytstudio playlists add <playlist-id> -v <video-id> -v <video-id> --execute
ytstudio playlists reorder <playlist-id> --by views --order desc --execute
ytstudio playlists remove <playlist-id> -v <video-id> --execute
ytstudio playlists delete <playlist-id> --execute -y         # -y skips the prompt
```

All playlist writes are dry-run until `--execute`. `delete` also prompts for
confirmation unless `-y/--yes` is passed; only add `-y` when running
non-interactively and the user has confirmed the deletion.

## Quota awareness

The YouTube Data API has a default budget of 10,000 units/day per project,
resetting at midnight Pacific. Rough costs:

| Operation | Cost |
|---|---|
| Read (list/show videos, comments, playlists; analytics) | ~1 unit |
| Write (update video, moderate comment, playlist insert/reorder, schedule broadcast) | ~50 units |
| Search (`playlists add --from-search`) | ~100 units/call |
| Upload (`videos upload`) | ~1600 units |

Before kicking off a large bulk run (e.g. `search-replace` over hundreds of
videos, or several uploads), estimate the cost and warn the user if it could
exhaust the daily quota. A `quotaExceeded` response (HTTP 403) means the budget
is spent until the next reset; long-running jobs (`videos upload`) stop cleanly
and report how many succeeded so they can be resumed later.

## Recommended workflow for an agent

1. Confirm setup once with `ytstudio status` (and `profile list` if multiple
   channels may be in play). Select the channel with `YTSTUDIO_PROFILE=` when
   scripting.
2. Gather state with read commands using `-o json` and parse the result.
3. For any change, run the command without `--execute` first, inspect the
   preview, and surface it to the user when the change is consequential or bulk.
4. Re-run the identical command with `--execute` to apply.
5. Mind the quota for bulk and upload operations.

When a flag or behavior is unclear, consult
[references/reference.md](references/reference.md) or `--help` rather than
assuming.
