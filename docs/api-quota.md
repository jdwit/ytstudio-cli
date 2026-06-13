# API quota

The YouTube Data API enforces a daily quota of **10 000 units per project**
by default. Most read operations (`videos.list`, `comments.list`, channel
info) cost 1 unit, while write operations like `videos.update`, playlist
edits, `liveBroadcasts.insert`/`update`, and `comments.setModerationStatus`
cost about 50 units each. `search.list` (behind `playlists add --from-search`)
is the notable exception at 100 units per call.

When you exceed the quota, the API returns HTTP 403 with a
`quotaExceeded` reason. ytstudio surfaces a clear error and exits.
Quota resets at midnight Pacific Time.

The **YouTube Analytics API** is a separate API with its own quota model
(query-cost based, far more generous in practice), so analytics calls do
not eat into the table below.

## Data API cost cheatsheet

| Operation                                    | Approx. quota cost |
|----------------------------------------------|--------------------|
| `videos.list`                                | 1 unit             |
| `commentThreads.list`                        | 1 unit             |
| `channels.list`                              | 1 unit             |
| `liveBroadcasts.list`                        | 1 unit             |
| `playlists.list`                             | 1 unit             |
| `playlistItems.list`                         | 1 unit             |
| `search.list`                                | 100 units          |
| `videos.update`                              | 50 units           |
| `comments.setModerationStatus`               | 50 units           |
| `comments.insert` (reply)                    | 50 units           |
| `playlists.insert` / `update` / `delete`     | 50 units           |
| `playlistItems.insert` / `update` / `delete` | 50 units           |
| `liveBroadcasts.insert`                      | 50 units           |
| `liveBroadcasts.update`                      | 50 units           |
| `liveBroadcasts.transition`                  | 50 units           |
| `thumbnails.set`                             | 50 units           |
| `videos.insert` (upload)                     | ~1600 units        |

At ~1600 units per upload, the default 10 000-unit daily budget covers about
six new videos per day. Use `ytstudio videos upload --max N` to cap a run
and avoid burning the budget you need for the rest of the day.

## Increasing the quota

In the Google Cloud Console, go to **IAM & Admin** :material-arrow-right:
**Quotas** and file a quota increase request for the YouTube Data API.
Google's response time varies; expect a couple of days.

Reference:
[YouTube quota documentation](https://developers.google.com/youtube/v3/getting-started#quota).
