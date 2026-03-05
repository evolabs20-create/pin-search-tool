from dataclasses import dataclass, field, asdict
from typing import Optional, List


@dataclass
class Pin:
    name: str
    pin_number: Optional[str] = None
    series: Optional[str] = None
    year: Optional[str] = None
    edition_size: Optional[str] = None
    image_url: Optional[str] = None
    source: str = ""
    source_url: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EbayListing:
    title: str
    price: float
    currency: str = "USD"
    ebay_url: str = ""
    image_url: Optional[str] = None
    condition: Optional[str] = None
    shipping_cost: Optional[float] = None
    seller_name: Optional[str] = None
    sold_date: Optional[str] = None
    end_date: Optional[str] = None
    listing_type: str = "active"  # "active" or "sold"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PriceSummary:
    query: str
    active_count: int = 0
    sold_count: int = 0
    active_low: Optional[float] = None
    active_high: Optional[float] = None
    active_avg: Optional[float] = None
    sold_low: Optional[float] = None
    sold_high: Optional[float] = None
    sold_avg: Optional[float] = None
    last_sold_date: Optional[str] = None
    cheapest_active_url: Optional[str] = None
    most_recent_sold_url: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
