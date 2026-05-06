"""Offline sample inputs and evidence for the runnable demo path."""

SAMPLE_PROJECT = {
    "description": (
        "A contained sci-fi thriller about a lunar mining crew that discovers "
        "an autonomous AI system has been rewriting mission records."
    ),
    "budget": 18_000_000,
    "genre": "Science Fiction",
    "platform": "hybrid",
    "comparables": ["Ex Machina", "Moon", "Arrival"],
    "target_audience": "adults 18-49, sci-fi thriller fans",
    "demo_mode": True,
}

SAMPLE_COMPARABLE_EVIDENCE = [
    {
        "title": "Ex Machina",
        "year": "2015",
        "budget": 15_000_000,
        "revenue": 36_900_000,
        "roi": 146.0,
        "rating": 7.6,
        "popularity": 41.2,
        "similar_titles": ["Annihilation", "Her", "Upgrade"],
    },
    {
        "title": "Moon",
        "year": "2009",
        "budget": 5_000_000,
        "revenue": 9_800_000,
        "roi": 96.0,
        "rating": 7.6,
        "popularity": 24.4,
        "similar_titles": ["Sunshine", "Coherence", "Europa Report"],
    },
    {
        "title": "Arrival",
        "year": "2016",
        "budget": 47_000_000,
        "revenue": 203_400_000,
        "roi": 332.77,
        "rating": 7.6,
        "popularity": 51.6,
        "similar_titles": ["Contact", "Interstellar", "Ad Astra"],
    },
]
