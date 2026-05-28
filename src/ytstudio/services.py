from ytstudio.api import get_authenticated_service


def get_data_service(profile: str | None = None):
    return get_authenticated_service("youtube", "v3", profile=profile)


def get_analytics_service(profile: str | None = None):
    return get_authenticated_service("youtubeAnalytics", "v2", profile=profile)
