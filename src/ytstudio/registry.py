"""YouTube Analytics API metrics and dimensions registry.

Single source of truth for all available metrics, dimensions, and their metadata.
Used for validation, documentation, and shell completion.

Reference: https://developers.google.com/youtube/analytics/metrics
           https://developers.google.com/youtube/analytics/dimensions
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    name: str
    description: str
    group: str
    core: bool = False
    monetary: bool = False  # requires yt-analytics-monetary.readonly scope


@dataclass(frozen=True)
class Dimension:
    name: str
    description: str
    group: str
    filter_only: bool = False  # can only be used as filter, not as dimension


# --- Metrics ---

METRICS: dict[str, Metric] = {m.name: m for m in [
    # View metrics
    Metric("views", "Number of times videos were viewed", "views", core=True),
    Metric("engagedViews", "Views past the initial seconds", "views", core=True),
    Metric("redViews", "Views by YouTube Premium members", "views"),
    Metric("viewerPercentage", "Percentage of logged-in viewers", "views", core=True),

    # Reach metrics
    Metric("videoThumbnailImpressions", "Times thumbnails were shown to viewers", "reach"),
    Metric("videoThumbnailImpressionsClickRate", "Percentage of impressions that became views (CTR)", "reach"),

    # Watch time metrics
    Metric("estimatedMinutesWatched", "Total minutes watched", "watch_time", core=True),
    Metric("estimatedRedMinutesWatched", "Minutes watched by YouTube Premium members", "watch_time"),
    Metric("averageViewDuration", "Average playback length in seconds", "watch_time", core=True),
    Metric("averageViewPercentage", "Average percentage of video watched", "watch_time"),

    # Engagement metrics
    Metric("likes", "Number of likes", "engagement", core=True),
    Metric("dislikes", "Number of dislikes", "engagement", core=True),
    Metric("comments", "Number of comments", "engagement", core=True),
    Metric("shares", "Number of shares via the Share button", "engagement", core=True),
    Metric("subscribersGained", "New subscribers gained", "engagement", core=True),
    Metric("subscribersLost", "Subscribers lost", "engagement", core=True),
    Metric("videosAddedToPlaylists", "Times videos were added to any playlist", "engagement"),
    Metric("videosRemovedFromPlaylists", "Times videos were removed from any playlist", "engagement"),

    # Card metrics
    Metric("cardImpressions", "Number of card impressions", "cards"),
    Metric("cardClicks", "Number of card clicks", "cards"),
    Metric("cardClickRate", "Card click-through rate", "cards"),
    Metric("cardTeaserImpressions", "Number of card teaser impressions", "cards"),
    Metric("cardTeaserClicks", "Number of card teaser clicks", "cards"),
    Metric("cardTeaserClickRate", "Card teaser click-through rate", "cards"),

    # Annotation metrics
    Metric("annotationImpressions", "Total annotation impressions", "annotations"),
    Metric("annotationClicks", "Number of annotation clicks", "annotations"),
    Metric("annotationClickThroughRate", "Annotation click-through rate", "annotations", core=True),
    Metric("annotationClosableImpressions", "Closable annotation impressions", "annotations"),
    Metric("annotationCloses", "Number of annotation closes", "annotations"),
    Metric("annotationCloseRate", "Annotation close rate", "annotations", core=True),
    Metric("annotationClickableImpressions", "Clickable annotation impressions", "annotations"),

    # Revenue metrics
    Metric("estimatedRevenue", "Estimated total net revenue", "revenue", core=True, monetary=True),
    Metric("estimatedAdRevenue", "Estimated ad net revenue", "revenue", monetary=True),
    Metric("grossRevenue", "Estimated gross revenue from ads", "revenue", monetary=True),
    Metric("estimatedRedPartnerRevenue", "Estimated YouTube Premium revenue", "revenue", monetary=True),
    Metric("monetizedPlaybacks", "Playbacks that showed at least one ad", "revenue", monetary=True),
    Metric("playbackBasedCpm", "Estimated gross revenue per 1000 playbacks", "revenue", monetary=True),
    Metric("adImpressions", "Number of verified ad impressions", "revenue", monetary=True),
    Metric("cpm", "Estimated gross revenue per 1000 ad impressions", "revenue", monetary=True),

    # Playlist metrics (in-playlist)
    Metric("playlistViews", "Video views in the context of a playlist", "playlist"),
    Metric("playlistStarts", "Number of times playlist playback was initiated", "playlist"),
    Metric("viewsPerPlaylistStart", "Average views per playlist start", "playlist"),
    Metric("averageTimeInPlaylist", "Average time (min) viewers spent in playlist", "playlist"),
    Metric("playlistSaves", "Net number of playlist saves", "playlist"),
    Metric("playlistEstimatedMinutesWatched", "Minutes watched in playlist context", "playlist"),
    Metric("playlistAverageViewDuration", "Average video view length in playlist context", "playlist"),

    # Unique viewers
    Metric("uniques", "Estimated unique viewers", "audience"),
]}

# --- Dimensions ---

DIMENSIONS: dict[str, Dimension] = {d.name: d for d in [
    # Time
    Dimension("day", "Date in YYYY-MM-DD format", "time"),
    Dimension("month", "Month in YYYY-MM format", "time"),

    # Geographic
    Dimension("country", "Two-letter ISO 3166-1 country code", "geographic"),
    Dimension("province", "US state (ISO 3166-2, requires country==US filter)", "geographic"),
    Dimension("city", "Estimated city (available from 2022-01-01)", "geographic"),
    Dimension("continent", "UN statistical region code", "geographic", filter_only=True),
    Dimension("subContinent", "UN sub-region code", "geographic", filter_only=True),
    Dimension("dma", "Nielsen Designated Market Area (3-digit)", "geographic"),

    # Content
    Dimension("video", "YouTube video ID", "content"),
    Dimension("playlist", "YouTube playlist ID", "content"),
    Dimension("group", "YouTube Analytics group ID", "content", filter_only=True),
    Dimension("creatorContentType", "Content type: shorts, videos, or live", "content"),

    # Traffic sources
    Dimension("insightTrafficSourceType", "Traffic source category", "traffic"),
    Dimension("insightTrafficSourceDetail", "Specific traffic source (search term, URL)", "traffic"),

    # Playback
    Dimension("playbackLocationType", "Where the video was played (watch page, embed, etc)", "playback"),
    Dimension("liveOrOnDemand", "Whether content was live or on-demand", "playback"),

    # Device
    Dimension("deviceType", "Device type (mobile, desktop, tablet, tv, etc)", "device"),
    Dimension("operatingSystem", "Operating system", "device"),

    # Audience
    Dimension("ageGroup", "Viewer age group", "audience"),
    Dimension("gender", "Viewer gender", "audience"),
    Dimension("subscribedStatus", "Whether viewer is subscribed", "audience"),
    Dimension("youtubeProduct", "YouTube product (main, shorts, music, etc)", "audience"),

    # Sharing
    Dimension("sharingService", "Service used to share (whatsapp, twitter, etc)", "sharing"),

    # Ads
    Dimension("adType", "Type of ad that ran during playback", "ads"),
]}

METRIC_GROUPS = sorted({m.group for m in METRICS.values()})
DIMENSION_GROUPS = sorted({d.group for d in DIMENSIONS.values()})


def find_closest_metric(name: str, max_distance: int = 3) -> str | None:
    """Find the closest matching metric name for typo suggestions."""
    return _find_closest(name, list(METRICS.keys()), max_distance)


def find_closest_dimension(name: str, max_distance: int = 3) -> str | None:
    """Find the closest matching dimension name for typo suggestions."""
    return _find_closest(name, list(DIMENSIONS.keys()), max_distance)


def _find_closest(name: str, candidates: list[str], max_distance: int) -> str | None:
    """Simple Levenshtein-based closest match."""
    best = None
    best_dist = max_distance + 1

    for candidate in candidates:
        dist = _levenshtein(name.lower(), candidate.lower())
        if dist < best_dist:
            best_dist = dist
            best = candidate

    return best if best_dist <= max_distance else None


def _levenshtein(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)

    if len(s2) == 0:
        return len(s1)

    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]


def validate_metrics(names: list[str]) -> list[str]:
    """Validate metric names, return list of errors."""
    errors = []
    for name in names:
        if name not in METRICS:
            suggestion = find_closest_metric(name)
            msg = f"Unknown metric '{name}'."
            if suggestion:
                msg += f" Did you mean '{suggestion}'?"
            errors.append(msg)
    return errors


def validate_dimensions(names: list[str]) -> list[str]:
    """Validate dimension names, return list of errors."""
    errors = []
    for name in names:
        if name not in DIMENSIONS:
            suggestion = find_closest_dimension(name)
            msg = f"Unknown dimension '{name}'."
            if suggestion:
                msg += f" Did you mean '{suggestion}'?"
            errors.append(msg)
    return errors
