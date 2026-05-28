# Analytics

`ytstudio analytics` queries the YouTube Analytics API: channel-wide totals,
per-video performance, and ad-hoc queries against the full metric and
dimension catalogue. Output defaults to a Rich table; pass `-o json` for
scripting.

## Common queries

```bash
ytstudio analytics overview                          # channel summary for the last 28 days
ytstudio analytics overview --days 7                 # rolling 7-day window
ytstudio analytics video <video-id>                  # one video's recent performance
ytstudio analytics video <video-id> --days 90        # longer window for one video
```

## Custom queries

`analytics query` is a thin wrapper over the YouTube Analytics
`reports.query` endpoint, so anything you can express against that API is
reachable from the CLI.

```bash
ytstudio analytics query \
    -m views,estimatedMinutesWatched,averageViewDuration \
    -d day \
    --start 2026-04-01 --end 2026-04-30

ytstudio analytics query \
    -m views -d country \
    --sort -views -n 10
```

Sort fields take a `-` prefix for descending. Use `-f key==value` (repeatable)
to filter, for example `-f video==dMH0bHeiRNg`.

Discover what is available:

```bash
ytstudio analytics metrics       # list every metric the API exposes
ytstudio analytics dimensions    # list every dimension the API exposes
```

Run `ytstudio analytics --help` (or open the
[Command reference](reference.md)) for every flag.

## Output

=== "Table"

    ```bash
    ytstudio analytics overview
    ```

=== "JSON"

    ```bash
    ytstudio analytics overview -o json | jq '.rows[0]'
    ```

## Quota

Analytics reads are cheap (1 unit per call against the Data API quota); you
can hit them often without worrying. See [API quota](api-quota.md) for the
full picture.
