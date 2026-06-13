# Comments

`ytstudio comments` lists comment threads and moderates them. It is built
for the scripted case where the YouTube Studio UI gets in the way:
filtering threads, approving or rejecting in bulk, exporting JSON for
downstream tooling.

## List

```bash
ytstudio comments list --video <video-id>
ytstudio comments list --video <video-id> -o json | jq

# Held queue, ordered chronologically
ytstudio comments list --video <video-id> --status held --sort time
```

`--status` accepts `published`, `held`, or `spam` (mapped internally to
YouTube's `published`, `heldForReview`, and `likelySpam` values). `--sort`
accepts `time` or `relevance`; the YouTube API only honours `relevance` for
a single video, so `--sort relevance` requires `--video <id>`. Omit
`--video` to list across the channel (time-sorted only).

## Approve held comments

```bash
ytstudio comments publish <comment-id> [<comment-id> ...]
```

`publish` takes one or more comment IDs and transitions each to
`published`.

## Reject

```bash
ytstudio comments reject <comment-id> [<comment-id> ...]
ytstudio comments reject <comment-id> --ban     # also ban the author
```

`reject` hides the comment from public view. Pass `--ban` to also ban the
author from the channel.

## Reply

```bash
ytstudio comments reply <comment-id> --text "Thanks for watching!"
```

`reply` posts a public reply to a comment and prints the new reply id.
Replies are flat on YouTube: `<comment-id>` must be a **top-level** comment
id (the `id` shown by `comments list`), not the id of another reply. Passing
a reply id (or an otherwise invalid id) returns a clear error. Like
`publish` and `reject`, `reply` executes immediately.

!!! note "Quota"

    `comments.setModerationStatus` and `comments.insert` (reply) each cost
    about 50 quota units per call. For larger moderation runs, see
    [API quota](api-quota.md).
