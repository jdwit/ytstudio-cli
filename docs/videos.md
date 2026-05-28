# Bulk video updates

The whole reason ytstudio exists. Use this when you need to change titles,
descriptions, or tags across many videos and YouTube Studio makes you
click each one. Also covers uploading whole batches of videos from a
directory of YAML sidecars.

## List and inspect

```bash
ytstudio videos list                       # most recent uploads
ytstudio videos list -n 100 -o json        # 100 items, JSON
ytstudio videos list --scheduled           # only videos scheduled for future publish
ytstudio videos show <video-id>            # full metadata for one video
```

`--scheduled` filters to private videos with a future `publishAt`, which is
the YouTube convention for "scheduled for release". Useful for sanity-checking
a queue you just uploaded.

## Update one video

```bash
ytstudio videos update <video-id> --title "New title"
ytstudio videos update <video-id> --description "New description"
ytstudio videos update <video-id> --tags one,two,three
```

`update` targets a single video; pass any combination of `--title`,
`--description`, or `--tags`.

## Search-and-replace across the channel

`videos search-replace` walks every video on the active channel, applies
the substitution, and shows what would change. It is **dry-run by
default**; pass `--execute` to actually update videos.

```bash
ytstudio videos search-replace --search "2024" --replace "2025" --field title
ytstudio videos search-replace \
    --search "old@email.com" --replace "new@email.com" --field description \
    --execute
ytstudio videos search-replace --search 'season \d' --replace 'season X' \
    --field title --regex
```

Flags:

- `--search`, `--replace` (required): the substitution.
- `--field` (required): `title` or `description`.
- `--regex`: treat `--search` as a Python regex.
- `--limit`: cap how many matches to act on (default 10).
- `--execute`: actually apply the changes.

!!! warning "Quota cost"

    `videos.update` costs about 50 quota units per video. A bulk run that
    touches 200 videos eats the default daily quota (10 000 units). See
    [API quota](api-quota.md) before kicking off large jobs.

## Upload a batch from sidecars

`videos upload` takes a video file or a directory, pairs each `.mp4`/`.mov`
with a sibling YAML sidecar describing its metadata, validates the lot, and
then uploads them in order. It is **dry-run by default**; pass `--execute`
to actually push to YouTube.

```bash
ytstudio videos upload ./outbox                       # dry-run preview
ytstudio videos upload ./outbox --execute             # actually upload
ytstudio videos upload ./outbox --execute --max 3     # cap the run (quota budget)
ytstudio videos upload ./outbox/single.mp4 --execute  # one specific video
```

### Directory layout

```
outbox/
  holiday.mp4
  holiday.yaml      # required
  holiday.jpg       # optional thumbnail (.jpg or .png), max 2 MB
  travel-vlog.mp4
  travel-vlog.yaml
```

The sidecar must share the video's basename. A thumbnail with the same
basename is picked up automatically; near-misses (different extension, wrong
case) fail fast with a clear error rather than silently uploading without a
thumbnail.

### Sidecar (`holiday.yaml`)

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

`publish_at` must be timezone-aware and in the future. If you set it, the
upload pipeline forces `privacy=private` because that is the only privacy
state YouTube accepts for scheduled releases.

### Resumability

After each successful upload the sidecar is patched with the resulting
`video_id` and an `uploaded_at` timestamp. Re-running `videos upload` on the
same directory only retries sidecars without a `video_id`, so partial runs
(quota exhaustion, network drop) are safe to resume.

If the write-back itself fails, the command prints the `video_id` to stdout
before exiting so you can paste it into the sidecar manually and avoid a
duplicate upload on the next run.

### Quota and rate limits

`videos.insert` costs roughly 1600 quota units, so on the default 10k/day
budget you can upload ~6 videos per day. Use `--max` to cap a run
explicitly. If the API returns `quotaExceeded` mid-run, the pipeline stops
cleanly, prints how many videos succeeded, and exits non-zero. See
[API quota](api-quota.md).
