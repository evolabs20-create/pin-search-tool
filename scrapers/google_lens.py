"""Google Lens image identification via SerpAPI."""

import logging
import os
import re
from typing import List

import requests

logger = logging.getLogger(__name__)

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")


def search_by_image(image_url: str) -> List[dict]:
    """
    Search Google Lens via SerpAPI with a publicly accessible image URL.
    Returns the visual_matches list from SerpAPI's response.
    """
    if not SERPAPI_KEY:
        logger.error("SERPAPI_KEY not set")
        return []

    try:
        resp = requests.get(
            "https://serpapi.com/search",
            params={
                "engine": "google_lens",
                "url": image_url,
                "api_key": SERPAPI_KEY,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("visual_matches", [])
    except Exception as e:
        logger.error(f"SerpAPI Google Lens error: {e}")
        return []


def extract_pin_candidates(results: List[dict]) -> List[str]:
    """
    From SerpAPI visual_matches, extract likely pin numbers or search terms
    that can be used to query PinPics/PinTradingDB.
    """
    candidates = []
    seen = set()

    for r in results:
        title = r.get("title", "")

        # Look for pin numbers (typically 3-6 digit numbers)
        numbers = re.findall(r'\b(\d{3,6})\b', title)
        for n in numbers:
            if n not in seen:
                seen.add(n)
                candidates.append(n)

        # Also extract the title as a search term if it looks pin-related
        lower = title.lower()
        if any(kw in lower for kw in ["pin", "disney", "trading", "limited edition"]):
            clean = re.sub(r'[^\w\s]', ' ', title).strip()
            if clean and clean not in seen:
                seen.add(clean)
                candidates.append(clean)

    return candidates


def build_identification(results: List[dict]) -> dict:
    """Build a summary identification dict from SerpAPI visual_matches."""
    titles = [r.get("title", "") for r in results[:5] if r.get("title")]
    thumbnail = next((r.get("thumbnail", "") for r in results if r.get("thumbnail")), "")
    description = titles[0] if titles else "No visual matches found"
    return {
        "source": "Google Lens (SerpAPI)",
        "description": description,
        "top_matches": titles[:5],
        "thumbnail": thumbnail,
    }
