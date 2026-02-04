"""Demo mode with mock data for screencasts."""

import os
from datetime import datetime, timedelta

DEMO_MODE = os.environ.get("YTS_DEMO", "").lower() in ("1", "true", "yes")

DEMO_CHANNEL = {
    "id": "UCdemo123456789",
    "title": "LuckyTV",
    "subscribers": 892000,
    "videos": 847,
    "views": 245000000,
}

DEMO_VIDEOS = [
    {
        "id": "vSzx36FRX-E",
        "title": "De Coalitie: Echt Al Lekker Op Weg - Yesilgöz, Bontenbal & Jetten",
        "published": datetime.now() - timedelta(days=5),
        "views": 37875,
        "likes": 1395,
        "comments": 118,
        "duration": "PT1M19S",
        "privacy": "public",
        "tags": ["LuckyTV", "coalitie", "Yesilgöz", "satire"],
        "description": "De kabinetsformatie is in volle gang...",
    },
    {
        "id": "abc123demo",
        "title": "Rutte's Laatste Dag - Een Compilatie",
        "published": datetime.now() - timedelta(days=45),
        "views": 1250000,
        "likes": 42000,
        "comments": 3200,
        "duration": "PT4M32S",
        "privacy": "public",
        "tags": ["LuckyTV", "Rutte", "compilatie"],
        "description": "Na 14 jaar is het voorbij...",
    },
    {
        "id": "def456demo",
        "title": "Thierry & de Flat Earth Society",
        "published": datetime.now() - timedelta(days=120),
        "views": 2100000,
        "likes": 68000,
        "comments": 5400,
        "duration": "PT2M15S",
        "privacy": "public",
        "tags": ["LuckyTV", "Baudet", "satire"],
        "description": "Een bijzondere ontmoeting...",
    },
    {
        "id": "ghi789demo",
        "title": "Willem-Alexander Leert TikTok",
        "published": datetime.now() - timedelta(days=200),
        "views": 3400000,
        "likes": 95000,
        "comments": 7800,
        "duration": "PT1M48S",
        "privacy": "public",
        "tags": ["LuckyTV", "koning", "TikTok"],
        "description": "De koning gaat met zijn tijd mee...",
    },
    {
        "id": "jkl012demo",
        "title": "Caroline van der Plas op de Boerderij",
        "published": datetime.now() - timedelta(days=90),
        "views": 1800000,
        "likes": 51000,
        "comments": 4100,
        "duration": "PT3M22S",
        "privacy": "public",
        "tags": ["LuckyTV", "BBB", "van der Plas"],
        "description": "Een dag uit het leven...",
    },
]

DEMO_ANALYTICS = {
    "views": 125000,
    "watch_time_hours": 8500,
    "subscribers_gained": 1250,
    "subscribers_lost": 180,
    "likes": 8900,
    "comments": 620,
    "shares": 3400,
    "avg_view_duration": "2:45",
    "ctr": 8.2,
    "impressions": 1520000,
}

DEMO_COMMENTS = [
    {
        "author": "Pietjeansen",
        "text": "LuckyTV is echt te goed 😂",
        "likes": 342,
        "published": datetime.now() - timedelta(hours=2),
    },
    {
        "author": "MediaWatcher",
        "text": "Eindelijk weer nieuwe content!",
        "likes": 156,
        "published": datetime.now() - timedelta(hours=5),
    },
    {
        "author": "Henk_uit_Almere",
        "text": "Dit is waarom ik YouTube betaal",
        "likes": 89,
        "published": datetime.now() - timedelta(hours=8),
    },
    {
        "author": "SatireFan2024",
        "text": "Sander is een genie",
        "likes": 234,
        "published": datetime.now() - timedelta(days=1),
    },
    {
        "author": "NLPolitiek",
        "text": "Te accuraat 🎯",
        "likes": 67,
        "published": datetime.now() - timedelta(days=1),
    },
]

DEMO_SEO = {
    "score": 78,
    "title_length": 65,
    "description_length": 420,
    "tags_count": 12,
    "has_thumbnail": True,
    "has_end_screen": True,
    "has_cards": True,
    "issues": [
        "Description could be longer (recommended: 500+ chars)",
        "Consider adding more tags (recommended: 15+)",
    ],
    "passed": [
        "Title length is optimal",
        "Has custom thumbnail",
        "End screen configured",
        "Cards added",
    ],
}


def get_demo_video(video_id: str) -> dict | None:
    """Get a demo video by ID."""
    for video in DEMO_VIDEOS:
        if video["id"] == video_id:
            return video
    # Return first video as fallback for any ID in demo mode
    return DEMO_VIDEOS[0] if DEMO_VIDEOS else None


def is_demo_mode() -> bool:
    """Check if demo mode is enabled."""
    return DEMO_MODE
