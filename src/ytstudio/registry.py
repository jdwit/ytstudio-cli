# Reference: https://developers.google.com/youtube/analytics/metrics
#            https://developers.google.com/youtube/analytics/dimensions

from dataclasses import dataclass
from enum import StrEnum


class MetricName(StrEnum):
    # View metrics
    VIEWS = "views"
    ENGAGED_VIEWS = "engagedViews"
    RED_VIEWS = "redViews"
    VIEWER_PERCENTAGE = "viewerPercentage"
    # Reach metrics
    VIDEO_THUMBNAIL_IMPRESSIONS = "videoThumbnailImpressions"
    VIDEO_THUMBNAIL_IMPRESSIONS_CLICK_RATE = "videoThumbnailImpressionsClickRate"
    # Watch time metrics
    ESTIMATED_MINUTES_WATCHED = "estimatedMinutesWatched"
    ESTIMATED_RED_MINUTES_WATCHED = "estimatedRedMinutesWatched"
    AVERAGE_VIEW_DURATION = "averageViewDuration"
    AVERAGE_VIEW_PERCENTAGE = "averageViewPercentage"
    # Engagement metrics
    LIKES = "likes"
    DISLIKES = "dislikes"
    COMMENTS = "comments"
    SHARES = "shares"
    SUBSCRIBERS_GAINED = "subscribersGained"
    SUBSCRIBERS_LOST = "subscribersLost"
    VIDEOS_ADDED_TO_PLAYLISTS = "videosAddedToPlaylists"
    VIDEOS_REMOVED_FROM_PLAYLISTS = "videosRemovedFromPlaylists"
    # Card metrics
    CARD_IMPRESSIONS = "cardImpressions"
    CARD_CLICKS = "cardClicks"
    CARD_CLICK_RATE = "cardClickRate"
    CARD_TEASER_IMPRESSIONS = "cardTeaserImpressions"
    CARD_TEASER_CLICKS = "cardTeaserClicks"
    CARD_TEASER_CLICK_RATE = "cardTeaserClickRate"
    # Annotation metrics
    ANNOTATION_IMPRESSIONS = "annotationImpressions"
    ANNOTATION_CLICKS = "annotationClicks"
    ANNOTATION_CLICK_THROUGH_RATE = "annotationClickThroughRate"
    ANNOTATION_CLOSABLE_IMPRESSIONS = "annotationClosableImpressions"
    ANNOTATION_CLOSES = "annotationCloses"
    ANNOTATION_CLOSE_RATE = "annotationCloseRate"
    ANNOTATION_CLICKABLE_IMPRESSIONS = "annotationClickableImpressions"
    # Revenue metrics
    ESTIMATED_REVENUE = "estimatedRevenue"
    ESTIMATED_AD_REVENUE = "estimatedAdRevenue"
    GROSS_REVENUE = "grossRevenue"
    ESTIMATED_RED_PARTNER_REVENUE = "estimatedRedPartnerRevenue"
    MONETIZED_PLAYBACKS = "monetizedPlaybacks"
    PLAYBACK_BASED_CPM = "playbackBasedCpm"
    AD_IMPRESSIONS = "adImpressions"
    CPM = "cpm"
    # Playlist metrics (in-playlist)
    PLAYLIST_VIEWS = "playlistViews"
    PLAYLIST_STARTS = "playlistStarts"
    VIEWS_PER_PLAYLIST_START = "viewsPerPlaylistStart"
    AVERAGE_TIME_IN_PLAYLIST = "averageTimeInPlaylist"
    PLAYLIST_SAVES = "playlistSaves"
    PLAYLIST_ESTIMATED_MINUTES_WATCHED = "playlistEstimatedMinutesWatched"
    PLAYLIST_AVERAGE_VIEW_DURATION = "playlistAverageViewDuration"
    # Unique viewers
    UNIQUES = "uniques"


class DimensionName(StrEnum):
    # Time
    DAY = "day"
    MONTH = "month"
    # Geographic
    COUNTRY = "country"
    PROVINCE = "province"
    CITY = "city"
    CONTINENT = "continent"
    SUB_CONTINENT = "subContinent"
    DMA = "dma"
    # Content
    VIDEO = "video"
    PLAYLIST = "playlist"
    GROUP = "group"
    CREATOR_CONTENT_TYPE = "creatorContentType"
    # Traffic sources
    INSIGHT_TRAFFIC_SOURCE_TYPE = "insightTrafficSourceType"
    INSIGHT_TRAFFIC_SOURCE_DETAIL = "insightTrafficSourceDetail"
    # Playback
    PLAYBACK_LOCATION_TYPE = "playbackLocationType"
    LIVE_OR_ON_DEMAND = "liveOrOnDemand"
    # Device
    DEVICE_TYPE = "deviceType"
    OPERATING_SYSTEM = "operatingSystem"
    # Audience
    AGE_GROUP = "ageGroup"
    GENDER = "gender"
    SUBSCRIBED_STATUS = "subscribedStatus"
    YOUTUBE_PRODUCT = "youtubeProduct"
    # Sharing
    SHARING_SERVICE = "sharingService"
    # Ads
    AD_TYPE = "adType"


@dataclass(frozen=True)
class Metric:
    name: MetricName
    description: str
    group: str
    core: bool = False
    monetary: bool = False  # requires yt-analytics-monetary.readonly scope


@dataclass(frozen=True)
class Dimension:
    name: DimensionName
    description: str
    group: str
    filter_only: bool = False  # can only be used as filter, not as dimension


# --- Metrics ---

METRICS: dict[MetricName, Metric] = {
    m.name: m
    for m in [
        # View metrics
        Metric(MetricName.VIEWS, "Number of times videos were viewed", "views", core=True),
        Metric(MetricName.ENGAGED_VIEWS, "Views past the initial seconds", "views", core=True),
        Metric(MetricName.RED_VIEWS, "Views by YouTube Premium members", "views"),
        Metric(MetricName.VIEWER_PERCENTAGE, "Percentage of logged-in viewers", "views", core=True),
        # Reach metrics
        Metric(
            MetricName.VIDEO_THUMBNAIL_IMPRESSIONS,
            "Times thumbnails were shown to viewers",
            "reach",
        ),
        Metric(
            MetricName.VIDEO_THUMBNAIL_IMPRESSIONS_CLICK_RATE,
            "Percentage of impressions that became views (CTR)",
            "reach",
        ),
        # Watch time metrics
        Metric(
            MetricName.ESTIMATED_MINUTES_WATCHED,
            "Total minutes watched",
            "watch_time",
            core=True,
        ),
        Metric(
            MetricName.ESTIMATED_RED_MINUTES_WATCHED,
            "Minutes watched by YouTube Premium members",
            "watch_time",
        ),
        Metric(
            MetricName.AVERAGE_VIEW_DURATION,
            "Average playback length in seconds",
            "watch_time",
            core=True,
        ),
        Metric(
            MetricName.AVERAGE_VIEW_PERCENTAGE,
            "Average percentage of video watched",
            "watch_time",
        ),
        # Engagement metrics
        Metric(MetricName.LIKES, "Number of likes", "engagement", core=True),
        Metric(MetricName.DISLIKES, "Number of dislikes", "engagement", core=True),
        Metric(MetricName.COMMENTS, "Number of comments", "engagement", core=True),
        Metric(MetricName.SHARES, "Number of shares via the Share button", "engagement", core=True),
        Metric(MetricName.SUBSCRIBERS_GAINED, "New subscribers gained", "engagement", core=True),
        Metric(MetricName.SUBSCRIBERS_LOST, "Subscribers lost", "engagement", core=True),
        Metric(
            MetricName.VIDEOS_ADDED_TO_PLAYLISTS,
            "Times videos were added to any playlist",
            "engagement",
        ),
        Metric(
            MetricName.VIDEOS_REMOVED_FROM_PLAYLISTS,
            "Times videos were removed from any playlist",
            "engagement",
        ),
        # Card metrics
        Metric(MetricName.CARD_IMPRESSIONS, "Number of card impressions", "cards"),
        Metric(MetricName.CARD_CLICKS, "Number of card clicks", "cards"),
        Metric(MetricName.CARD_CLICK_RATE, "Card click-through rate", "cards"),
        Metric(MetricName.CARD_TEASER_IMPRESSIONS, "Number of card teaser impressions", "cards"),
        Metric(MetricName.CARD_TEASER_CLICKS, "Number of card teaser clicks", "cards"),
        Metric(MetricName.CARD_TEASER_CLICK_RATE, "Card teaser click-through rate", "cards"),
        # Annotation metrics
        Metric(MetricName.ANNOTATION_IMPRESSIONS, "Total annotation impressions", "annotations"),
        Metric(MetricName.ANNOTATION_CLICKS, "Number of annotation clicks", "annotations"),
        Metric(
            MetricName.ANNOTATION_CLICK_THROUGH_RATE,
            "Annotation click-through rate",
            "annotations",
            core=True,
        ),
        Metric(
            MetricName.ANNOTATION_CLOSABLE_IMPRESSIONS,
            "Closable annotation impressions",
            "annotations",
        ),
        Metric(MetricName.ANNOTATION_CLOSES, "Number of annotation closes", "annotations"),
        Metric(MetricName.ANNOTATION_CLOSE_RATE, "Annotation close rate", "annotations", core=True),
        Metric(
            MetricName.ANNOTATION_CLICKABLE_IMPRESSIONS,
            "Clickable annotation impressions",
            "annotations",
        ),
        # Revenue metrics
        Metric(
            MetricName.ESTIMATED_REVENUE,
            "Estimated total net revenue",
            "revenue",
            core=True,
            monetary=True,
        ),
        Metric(
            MetricName.ESTIMATED_AD_REVENUE,
            "Estimated ad net revenue",
            "revenue",
            monetary=True,
        ),
        Metric(
            MetricName.GROSS_REVENUE,
            "Estimated gross revenue from ads",
            "revenue",
            monetary=True,
        ),
        Metric(
            MetricName.ESTIMATED_RED_PARTNER_REVENUE,
            "Estimated YouTube Premium revenue",
            "revenue",
            monetary=True,
        ),
        Metric(
            MetricName.MONETIZED_PLAYBACKS,
            "Playbacks that showed at least one ad",
            "revenue",
            monetary=True,
        ),
        Metric(
            MetricName.PLAYBACK_BASED_CPM,
            "Estimated gross revenue per 1000 playbacks",
            "revenue",
            monetary=True,
        ),
        Metric(
            MetricName.AD_IMPRESSIONS,
            "Number of verified ad impressions",
            "revenue",
            monetary=True,
        ),
        Metric(
            MetricName.CPM,
            "Estimated gross revenue per 1000 ad impressions",
            "revenue",
            monetary=True,
        ),
        # Playlist metrics (in-playlist)
        Metric(MetricName.PLAYLIST_VIEWS, "Video views in the context of a playlist", "playlist"),
        Metric(
            MetricName.PLAYLIST_STARTS,
            "Number of times playlist playback was initiated",
            "playlist",
        ),
        Metric(
            MetricName.VIEWS_PER_PLAYLIST_START,
            "Average views per playlist start",
            "playlist",
        ),
        Metric(
            MetricName.AVERAGE_TIME_IN_PLAYLIST,
            "Average time (min) viewers spent in playlist",
            "playlist",
        ),
        Metric(MetricName.PLAYLIST_SAVES, "Net number of playlist saves", "playlist"),
        Metric(
            MetricName.PLAYLIST_ESTIMATED_MINUTES_WATCHED,
            "Minutes watched in playlist context",
            "playlist",
        ),
        Metric(
            MetricName.PLAYLIST_AVERAGE_VIEW_DURATION,
            "Average video view length in playlist context",
            "playlist",
        ),
        # Unique viewers
        Metric(MetricName.UNIQUES, "Estimated unique viewers", "audience"),
    ]
}

# --- Dimensions ---

DIMENSIONS: dict[DimensionName, Dimension] = {
    d.name: d
    for d in [
        # Time
        Dimension(DimensionName.DAY, "Date in YYYY-MM-DD format", "time"),
        Dimension(DimensionName.MONTH, "Month in YYYY-MM format", "time"),
        # Geographic
        Dimension(DimensionName.COUNTRY, "Two-letter ISO 3166-1 country code", "geographic"),
        Dimension(
            DimensionName.PROVINCE,
            "US state (ISO 3166-2, requires country==US filter)",
            "geographic",
        ),
        Dimension(DimensionName.CITY, "Estimated city (available from 2022-01-01)", "geographic"),
        Dimension(
            DimensionName.CONTINENT, "UN statistical region code", "geographic", filter_only=True
        ),
        Dimension(
            DimensionName.SUB_CONTINENT, "UN sub-region code", "geographic", filter_only=True
        ),
        Dimension(DimensionName.DMA, "Nielsen Designated Market Area (3-digit)", "geographic"),
        # Content
        Dimension(DimensionName.VIDEO, "YouTube video ID", "content"),
        Dimension(DimensionName.PLAYLIST, "YouTube playlist ID", "content"),
        Dimension(DimensionName.GROUP, "YouTube Analytics group ID", "content", filter_only=True),
        Dimension(
            DimensionName.CREATOR_CONTENT_TYPE,
            "Content type: shorts, videos, or live",
            "content",
        ),
        # Traffic sources
        Dimension(DimensionName.INSIGHT_TRAFFIC_SOURCE_TYPE, "Traffic source category", "traffic"),
        Dimension(
            DimensionName.INSIGHT_TRAFFIC_SOURCE_DETAIL,
            "Specific traffic source (search term, URL)",
            "traffic",
        ),
        # Playback
        Dimension(
            DimensionName.PLAYBACK_LOCATION_TYPE,
            "Where the video was played (watch page, embed, etc)",
            "playback",
        ),
        Dimension(
            DimensionName.LIVE_OR_ON_DEMAND,
            "Whether content was live or on-demand",
            "playback",
        ),
        # Device
        Dimension(
            DimensionName.DEVICE_TYPE,
            "Device type (mobile, desktop, tablet, tv, etc)",
            "device",
        ),
        Dimension(DimensionName.OPERATING_SYSTEM, "Operating system", "device"),
        # Audience
        Dimension(DimensionName.AGE_GROUP, "Viewer age group", "audience"),
        Dimension(DimensionName.GENDER, "Viewer gender", "audience"),
        Dimension(DimensionName.SUBSCRIBED_STATUS, "Whether viewer is subscribed", "audience"),
        Dimension(
            DimensionName.YOUTUBE_PRODUCT,
            "YouTube product (main, shorts, music, etc)",
            "audience",
        ),
        # Sharing
        Dimension(
            DimensionName.SHARING_SERVICE,
            "Service used to share (whatsapp, twitter, etc)",
            "sharing",
        ),
        # Ads
        Dimension(DimensionName.AD_TYPE, "Type of ad that ran during playback", "ads"),
    ]
}

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
