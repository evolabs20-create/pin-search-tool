"""eBay scraper for Disney pin pricing data."""

import os
import requests
from typing import List, Optional
from urllib.parse import quote

from scrapers.base import BaseScraper
from models import Pin


class eBayScraper(BaseScraper):
    """Scraper for eBay Disney pin listings."""
    
    source_name = "ebay"
    base_url = "https://api.ebay.com"
    
    def __init__(self, delay: float = 1.5, sandbox: bool = False):
        super().__init__(delay)
        self.sandbox = sandbox
        
        # Use sandbox or production credentials
        if sandbox:
            self.app_id = os.environ.get("EBAY_SANDBOX_APP_ID", "")
            self.base_url = "https://api.sandbox.ebay.com"
        else:
            self.app_id = os.environ.get("EBAY_APP_ID", "")
            
        if not self.app_id:
            print(f"Warning: eBay {'Sandbox ' if sandbox else ''}App ID not set")
    
    def _get_oauth_token(self) -> Optional[str]:
        """Get OAuth token for eBay API."""
        # For Finding API (public), we can use App ID directly
        # For Buy API, we need OAuth
        return None
    
    def search(self, query: str, limit: int = 20) -> List[Pin]:
        """Search eBay for Disney pins."""
        if not self.app_id:
            print("eBay App ID not configured. Skipping.")
            return []
        
        # Use eBay Finding API
        url = "https://svcs.ebay.com/services/search/FindingService/v1"
        
        params = {
            "OPERATION-NAME": "findItemsByKeywords",
            "SERVICE-VERSION": "1.0.0",
            "SECURITY-APPNAME": self.app_id,
            "RESPONSE-DATA-FORMAT": "JSON",
            "keywords": f"Disney pin {query}",
            "paginationInput.entriesPerPage": min(limit, 100),
            "sortOrder": "BestMatch",
        }
        
        headers = {
            "X-EBAY-SOA-SECURITY-APPNAME": self.app_id,
        }
        
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            pins = []
            search_result = data.get("findItemsByKeywordsResponse", [{}])[0]
            items = search_result.get("searchResult", [{}])[0].get("item", [])
            
            for item in items:
                try:
                    pin = self._parse_item(item)
                    if pin:
                        pins.append(pin)
                except Exception as e:
                    print(f"Error parsing eBay item: {e}")
                    continue
            
            return pins[:limit]
            
        except Exception as e:
            print(f"eBay search error: {e}")
            return []
    
    def lookup(self, pin_number: str, limit: int = 20) -> List[Pin]:
        """Look up a specific pin by number on eBay."""
        # eBay doesn't have standardized pin numbers like PinPics
        # So we search by the pin number as a keyword
        return self.search(f"pin {pin_number}", limit)
    
    def search_sold(self, query: str, limit: int = 20) -> List[Pin]:
        """Search for sold/completed listings to get price history."""
        if not self.app_id:
            print("eBay App ID not configured. Skipping.")
            return []
        
        url = "https://svcs.ebay.com/services/search/FindingService/v1"
        
        params = {
            "OPERATION-NAME": "findCompletedItems",
            "SERVICE-VERSION": "1.0.0",
            "SECURITY-APPNAME": self.app_id,
            "RESPONSE-DATA-FORMAT": "JSON",
            "keywords": f"Disney pin {query}",
            "paginationInput.entriesPerPage": min(limit, 100),
            "sortOrder": "EndTimeSoonest",
        }
        
        headers = {
            "X-EBAY-SOA-SECURITY-APPNAME": self.app_id,
        }
        
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            pins = []
            search_result = data.get("findCompletedItemsResponse", [{}])[0]
            items = search_result.get("searchResult", [{}])[0].get("item", [])
            
            for item in items:
                try:
                    pin = self._parse_item(item, sold=True)
                    if pin:
                        pins.append(pin)
                except Exception as e:
                    print(f"Error parsing eBay sold item: {e}")
                    continue
            
            return pins[:limit]
            
        except Exception as e:
            print(f"eBay sold search error: {e}")
            return []
    
    def _parse_item(self, item: dict, sold: bool = False) -> Optional[Pin]:
        """Parse an eBay item into a Pin object."""
        try:
            title = item.get("title", [""])[0] if isinstance(item.get("title"), list) else item.get("title", "")
            
            # Extract pin number if present in title
            import re
            pin_number = None
            pin_match = re.search(r'#?(\d{4,6})', title)
            if pin_match:
                pin_number = pin_match.group(1)
            
            # Get price
            selling_status = item.get("sellingStatus", [{}])[0]
            current_price = selling_status.get("currentPrice", [{}])[0]
            price_value = current_price.get("__value__", "N/A")
            price_currency = current_price.get("@currencyId", "USD")
            
            # Get image
            gallery_url = item.get("galleryURL", [""])[0] if isinstance(item.get("galleryURL"), list) else item.get("galleryURL", "")
            
            # Get item URL
            view_url = item.get("viewItemURL", [""])[0] if isinstance(item.get("viewItemURL"), list) else item.get("viewItemURL", "")
            
            # Build description with price info
            listing_type = "SOLD" if sold else "ACTIVE"
            edition_size = f"{price_value} {price_currency} ({listing_type})"
            
            return Pin(
                name=title,
                pin_number=pin_number,
                series="eBay Listing",
                year=None,
                edition_size=edition_size,
                image_url=gallery_url if gallery_url else None,
                source="ebay",
                source_url=view_url
            )
            
        except Exception as e:
            print(f"Error parsing eBay item: {e}")
            return None
