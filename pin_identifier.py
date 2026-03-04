"""Use Claude Vision to identify Disney pins from photos."""

import base64
import logging
import os
import re
from pathlib import Path
from typing import List

import anthropic

logger = logging.getLogger(__name__)

PROMPT = """You are a Disney pin identification expert. Analyze this image of a Disney pin and extract:

1. **Characters**: Which Disney characters are shown (e.g., Mickey Mouse, Elsa, Stitch)
2. **Theme/Set**: Any visible set name, event, or theme (e.g., "Hidden Mickey", "Haunted Mansion", "50th Anniversary")
3. **Text on pin**: Any text, numbers, or logos visible on the pin
4. **Pin number**: If a pin number is visible (often on the back or edge)
5. **Edition type**: If visible (LE, OE, Limited Edition, etc.)
6. **Year**: If a year is visible
7. **Park/Origin**: If identifiable (WDW, DLR, Tokyo Disney, etc.)

Based on your analysis, provide 2-3 search queries that would best find this pin in a database. Make queries specific enough to narrow results but not so specific they miss the pin.

Respond in this exact JSON format:
{
    "characters": ["character1", "character2"],
    "theme": "theme or set name if identifiable",
    "text_on_pin": "any visible text",
    "pin_number": "number if visible, null otherwise",
    "edition": "edition type if visible",
    "year": "year if visible",
    "origin": "park/origin if identifiable",
    "description": "brief one-line description of the pin",
    "search_queries": ["query 1", "query 2", "query 3"]
}

Only respond with the JSON, no other text."""


def identify_pin(image_path: str, api_key: str = None) -> dict:
    """Analyze a pin image with Claude Vision and return identification data."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    # Read and encode image
    with open(path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    mime = _guess_mime(path)

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime,
                        "data": image_data,
                    },
                },
                {
                    "type": "text",
                    "text": PROMPT,
                },
            ],
        }],
    )

    # Parse response
    text = message.content[0].text.strip()

    # Extract JSON from response (handle markdown code blocks)
    json_match = re.search(r"\{[\s\S]*\}", text)
    if not json_match:
        logger.error(f"Could not parse Claude response: {text}")
        return {"search_queries": [], "description": text}

    import json
    try:
        result = json.loads(json_match.group())
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON from Claude: {text}")
        return {"search_queries": [], "description": text}

    logger.info(f"Pin identified: {result.get('description', 'unknown')}")
    return result


def get_search_queries(image_path: str, api_key: str = None) -> List[str]:
    """Convenience: just get the search queries for a pin image."""
    result = identify_pin(image_path, api_key)

    queries = result.get("search_queries", [])

    # Also try pin number directly if found
    pin_number = result.get("pin_number")
    if pin_number and pin_number not in queries:
        queries.insert(0, pin_number)

    # Fallback: build a query from characters + theme
    if not queries:
        parts = []
        chars = result.get("characters", [])
        if chars:
            parts.append(" ".join(chars[:2]))
        theme = result.get("theme")
        if theme:
            parts.append(theme)
        if parts:
            queries.append(" ".join(parts))

    return queries, result


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")
