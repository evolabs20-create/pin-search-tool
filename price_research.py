"""Price research module — aggregates eBay active and sold listing data."""

from typing import List, Optional

from models import EbayListing, PriceSummary
from scrapers.ebay import eBayScraper


def research_pin(query: str, active_limit: int = 40, sold_limit: int = 40) -> dict:
    """Run price research for a query. Returns summary + listing details."""
    scraper = eBayScraper()

    active = scraper.search_listings(query, limit=active_limit)
    sold = scraper.search_sold_listings(query, limit=sold_limit)

    summary = _compute_summary(query, active, sold)

    return {
        "summary": summary.to_dict(),
        "active_listings": [l.to_dict() for l in active],
        "sold_listings": [l.to_dict() for l in sold],
    }


def _compute_summary(
    query: str,
    active: List[EbayListing],
    sold: List[EbayListing],
) -> PriceSummary:
    """Compute price summary from active and sold listings."""
    summary = PriceSummary(query=query)

    if active:
        prices = [l.price for l in active if l.price > 0]
        if prices:
            summary.active_count = len(prices)
            summary.active_low = round(min(prices), 2)
            summary.active_high = round(max(prices), 2)
            summary.active_avg = round(sum(prices) / len(prices), 2)
            # Cheapest active listing
            cheapest = min(active, key=lambda l: l.price if l.price > 0 else float("inf"))
            summary.cheapest_active_url = cheapest.ebay_url

    if sold:
        prices = [l.price for l in sold if l.price > 0]
        if prices:
            summary.sold_count = len(prices)
            summary.sold_low = round(min(prices), 2)
            summary.sold_high = round(max(prices), 2)
            summary.sold_avg = round(sum(prices) / len(prices), 2)
            # Most recent sold listing (first in list since sorted by EndTimeSoonest)
            most_recent = sold[0]
            summary.most_recent_sold_url = most_recent.ebay_url
            summary.last_sold_date = most_recent.sold_date

    return summary
