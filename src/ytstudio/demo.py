"""Demo mode with mock data for screencasts."""

import os
from datetime import datetime, timedelta

DEMO_MODE = os.environ.get("YTS_DEMO", "").lower() in ("1", "true", "yes")

# Demo data based on Fireship (https://youtube.com/@Fireship)
# Used with appreciation for educational purposes

DEMO_CHANNEL = {
    "id": "UCsBjURrPoezykLs9EqgamOA",
    "title": "Fireship",
    "subscribers": 4060000,
    "videos": 850,
    "views": 654000000,
}

DEMO_VIDEOS = [
    {
        "id": "zQnBQ4tB3ZA",
        "title": "TypeScript in 100 Seconds",
        "published": datetime(2020, 11, 25),
        "views": 3200000,
        "likes": 98000,
        "comments": 2400,
        "duration": "PT2M1S",
        "privacy": "public",
        "tags": ["typescript", "javascript", "100SecondsOfCode", "programming"],
        "description": "Learn the basics of TypeScript in 100 seconds...",
    },
    {
        "id": "lHhRhPV--G0",
        "title": "Flutter in 100 Seconds",
        "published": datetime(2020, 4, 14),
        "views": 2100000,
        "likes": 72000,
        "comments": 1800,
        "duration": "PT2M8S",
        "privacy": "public",
        "tags": ["flutter", "dart", "mobile", "100SecondsOfCode"],
        "description": "Build apps on iOS, Android, the web, and desktop with Flutter...",
    },
    {
        "id": "rf60MejMz3E",
        "title": "Recursion in 100 Seconds",
        "published": datetime(2019, 12, 30),
        "views": 1800000,
        "likes": 65000,
        "comments": 1500,
        "duration": "PT1M48S",
        "privacy": "public",
        "tags": ["recursion", "algorithms", "100SecondsOfCode", "compsci"],
        "description": "Learn how recursion works in 100 seconds...",
    },
    {
        "id": "Ata9cSC2WpM",
        "title": "React in 100 Seconds",
        "published": datetime(2021, 5, 12),
        "views": 4500000,
        "likes": 125000,
        "comments": 3200,
        "duration": "PT2M15S",
        "privacy": "public",
        "tags": ["react", "javascript", "frontend", "100SecondsOfCode"],
        "description": "Learn the basics of React in 100 seconds...",
    },
    {
        "id": "w7ejDZ8SWv8",
        "title": "God-Tier Developer Roadmap",
        "published": datetime(2022, 8, 15),
        "views": 6800000,
        "likes": 215000,
        "comments": 8500,
        "duration": "PT11M42S",
        "privacy": "public",
        "tags": ["roadmap", "developer", "career", "programming"],
        "description": "A mass extinction satisfies both business and our lizard brain...",
    },
]

DEMO_ANALYTICS = {
    "views": 2500000,
    "watch_time_hours": 185000,
    "subscribers_gained": 45000,
    "subscribers_lost": 3200,
    "likes": 89000,
    "comments": 6200,
    "shares": 12000,
    "avg_view_duration": "3:45",
    "ctr": 12.5,
    "impressions": 20000000,
}

DEMO_COMMENTS = [
    {
        "author": "CodeNewbie",
        "text": "This is the best explanation I've ever seen! 🔥",
        "likes": 1542,
        "published": datetime.now() - timedelta(hours=2),
    },
    {
        "author": "DevSenior",
        "text": "100 seconds well spent. Subscribed!",
        "likes": 856,
        "published": datetime.now() - timedelta(hours=5),
    },
    {
        "author": "TechEnthusiast",
        "text": "Fireship videos are like coffee for developers ☕",
        "likes": 2341,
        "published": datetime.now() - timedelta(hours=8),
    },
    {
        "author": "JuniorDev2024",
        "text": "Finally understand this after watching 10 other tutorials",
        "likes": 634,
        "published": datetime.now() - timedelta(days=1),
    },
    {
        "author": "FullStackFan",
        "text": "The production quality is insane for these short videos",
        "likes": 421,
        "published": datetime.now() - timedelta(days=1),
    },
]

DEMO_SEO = {
    "score": 92,
    "title_length": 28,
    "description_length": 850,
    "tags_count": 15,
    "has_thumbnail": True,
    "has_end_screen": True,
    "has_cards": True,
    "issues": [
        "Consider a longer title for better discoverability",
    ],
    "passed": [
        "Strong keyword in title",
        "Description well-optimized",
        "Good tag coverage",
        "Custom thumbnail",
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
