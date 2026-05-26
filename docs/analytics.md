# Analytics

`ytstudio analytics` queries the YouTube Analytics API: totals, daily
breakdowns, per-video and per-country views, watch time, and the rest.
Output defaults to a Rich table; pass `-o json` for scripting.

## Common queries

```bash
ytstudio analytics overview                # channel summary for the last period
ytstudio analytics top --by views          # top videos by views
ytstudio analytics video <video-id>        # one video's recent performance
ytstudio analytics by-country --metric views
ytstudio analytics by-day --metric views   # last 7 days
```

Run `ytstudio analytics --help` (or open the
[Command reference](reference.md)) for every flag.

## Output

=== "Table"

    ```bash
    ytstudio analytics top --by views
    ```

=== "JSON"

    ```bash
    ytstudio analytics top --by views -o json | jq '.rows[0]'
    ```

## Quota

Analytics reads are cheap (1 unit per call); you can hit them often without
worrying. See [API quota](api-quota.md) for the full picture.
