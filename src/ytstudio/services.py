from ytstudio.api import get_authenticated_service
from ytstudio.demo import DemoAnalyticsService, DemoDataService, is_demo_mode


def get_data_service():
    if is_demo_mode():
        return DemoDataService()
    return get_authenticated_service("youtube", "v3")


def get_analytics_service():
    if is_demo_mode():
        return DemoAnalyticsService()
    return get_authenticated_service("youtubeAnalytics", "v2")
