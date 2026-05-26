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
ytstudio comments list --video <video-id> --moderation-status held --order time
```

`--moderation-status` accepts `published`, `held`, or `spam` (mapped
internally to YouTube's `published`, `heldForReview`, and `likelySpam`
values).

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

!!! note "Quota"

    `comments.setModerationStatus` costs about 50 quota units per call. For
    larger moderation runs, see [API quota](api-quota.md).
