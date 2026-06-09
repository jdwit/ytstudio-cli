# Playlists

Bulk operations on YouTube playlists from the terminal. YouTube Studio is fine
for tweaking one playlist; this set of commands is for the cases where you
want to add a search query's worth of videos at once, reorder by views, or
sync a manifest across many channels.

## List and inspect

```bash
ytstudio playlists list                                  # your playlists
ytstudio playlists list -n 200 -o json                   # 200, JSON
ytstudio playlists list -o csv > playlists.csv           # export

ytstudio playlists show PL_xxx                           # one playlist
ytstudio playlists show PL_xxx --items                   # plus the first 50 items
ytstudio playlists items PL_xxx                          # full item listing
ytstudio playlists items PL_xxx -n 500 -o csv            # paginated CSV
```

`list` sorts locally with `--sort date|title|count`. `items` shows the
playlist item id (`PLPLI...`) you need for `remove --item` and `reorder`.

## Create, update, delete

```bash
ytstudio playlists create --title "Best of 2026" --privacy public --execute
ytstudio playlists update PL_xxx --title "Best of 2026 (final)" --execute
ytstudio playlists delete PL_xxx --execute              # asks to confirm
ytstudio playlists delete PL_xxx --execute --yes        # no prompt (CI / agents)
```

Mutations are **dry-run by default**; add `--execute` to apply. `update` only
sends the fields you pass; everything else is re-specified from the current
snippet so YouTube does not silently nuke a field by omitting it.

The channel's auto-uploads playlist (`UU...` belonging to your channel) is
always refused. The check resolves the canonical uploads id via
`channels.list(mine=True).contentDetails.relatedPlaylists.uploads`, so a
random other playlist id that happens to start with `UU` is not blocked.

## Bulk add

`add` accepts explicit video ids, a search query, or both. The combined batch
is capped by `--limit`.

```bash
ytstudio playlists add PL_xxx -v vid_a -v vid_b --execute
ytstudio playlists add PL_xxx --from-search "shorts compilation" -n 20 --execute
ytstudio playlists add PL_xxx -v vid_a --from-search "topic" -n 10 --execute
ytstudio playlists add PL_xxx -v vid_a -v vid_b --position 5 --execute
```

`--from-search` calls `search.list(forMine=True, type=video, q=...)`.
`--position N` inserts the first video at position `N`, the second at `N+1`,
and so on, so the on-playlist order matches the CLI order. `--note "text"`
attaches a per-item note.

!!! warning "Quota cost"

    `playlistItems.insert` costs 50 quota units per video. The default daily
    quota (10 000 units) covers ~200 inserts. `search.list` costs an
    additional 100 units per call. See [API quota](api-quota.md).

## Bulk remove

```bash
ytstudio playlists remove PL_xxx --item PLPLI_a --item PLPLI_b --execute
ytstudio playlists remove PL_xxx --video vid_a --execute
```

`--video` resolves to every playlist item for that video in the playlist and
removes all occurrences; pass the same id once even if it appears multiple
times.

## Reorder

`reorder` sorts the playlist by views, likes, publish date, or title.

```bash
ytstudio playlists reorder PL_xxx --by views --execute
ytstudio playlists reorder PL_xxx --by title --order asc --execute
```

The playlist must be set to **Manual** sort in YouTube Studio
(Settings -> Sort by -> Manual). If it is not, YouTube returns
`manualSortRequired` and the command stops with an actionable message.

Writes that become no-ops once earlier moves have shifted neighbouring items
are skipped, so a full reverse on N items costs at most `N - 1` writes
instead of `N`.

## Output formats

All read commands take `--output table|json|csv`. CSV uses Python's
`csv.writer`, so titles with commas, newlines, or quotes survive round-trips
through Excel and `pandas.read_csv`.

## Power moves

```bash
# Curate a "watch later" from a search
ytstudio playlists add PL_watchlater --from-search "rust async" -n 30 --execute

# Move the all-time top by views to the front
ytstudio playlists reorder PL_pinned --by views --execute

# Promote a single video to the top of an existing playlist
ytstudio playlists add PL_pinned -v <new-banger> --position 0 --execute
```
