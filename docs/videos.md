# Bulk video updates

The whole reason ytstudio exists. Use this when you need to change titles,
descriptions, or tags across many videos and YouTube Studio makes you
click each one.

## List and inspect

```bash
ytstudio videos list                       # most recent uploads
ytstudio videos list -n 100 -o json        # 100 items, JSON
ytstudio videos show <video-id>            # full metadata for one video
```

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

## Demo mode

Run any video command without authenticating by setting `YTSTUDIO_DEMO=1`:

```bash
YTSTUDIO_DEMO=1 ytstudio videos list
```

Demo mode uses bundled fixtures and never reaches the real API.
