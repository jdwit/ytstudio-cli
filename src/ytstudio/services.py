from ytstudio.api import get_authenticated_service


def get_data_service(profile: str | None = None):
    # Local import keeps the real auth path zero-overhead when demo mode is off.
    from ytstudio.demo_service import FakeYouTubeService, is_demo_mode  # noqa: PLC0415

    if is_demo_mode():
        return FakeYouTubeService()
    return get_authenticated_service("youtube", "v3", profile=profile)


def get_analytics_service(profile: str | None = None):
    from ytstudio.demo_service import FakeAnalyticsService, is_demo_mode  # noqa: PLC0415

    if is_demo_mode():
        return FakeAnalyticsService()
    return get_authenticated_service("youtubeAnalytics", "v2", profile=profile)
