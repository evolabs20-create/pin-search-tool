import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Pin
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class PinPicsScraper(BaseScraper):
    source_name = "PinPics"
    base_url = "https://pinpics.com"

    def search(self, query: str, limit: int = 20) -> List[Pin]:
        """Search PinPics pin database by keyword."""
        url = f"{self.base_url}/pins/"
        html = self.fetch(url, params={"filter_name": query, "sortdirection": "desc"})
        if not html:
            logger.warning("PinPics search returned no response")
            return []
        return self._parse_search_results(html, limit)

    def lookup(self, pin_number: str, limit: int = 20) -> List[Pin]:
        """Look up a specific pin by number on PinPics."""
        # Try direct detail page
        url = f"{self.base_url}/pin/{pin_number}/"
        html = self.fetch(url)
        if html:
            pin = self._parse_detail_page(html, url)
            if pin:
                return [pin]

        # Fall back to searching by number
        return self.search(pin_number, limit)

    def _parse_search_results(self, html: str, limit: int) -> List[Pin]:
        soup = BeautifulSoup(html, "lxml")
        pins = []

        # Each pin is a <li class="ipsDataItem" data-pin-wrapper="{id}">
        for item in soup.select("li.ipsDataItem[data-pin-wrapper]"):
            pin = self._parse_card(item)
            if pin:
                pins.append(pin)
                if len(pins) >= limit:
                    break

        return pins

    def _parse_card(self, item) -> Optional[Pin]:
        try:
            pin_id = item.get("data-pin-wrapper", "")

            # Image from .tbPinsGridImage img
            image_url = None
            img = item.select_one("div.tbPinsGridImage img")
            if img and img.get("src"):
                image_url = img["src"]

            # Detail URL from the first link
            detail_url = None
            a_tag = item.select_one("div.tbPinsGridImage a[href]")
            if a_tag:
                detail_url = a_tag["href"]

            # Pin number from h4 link (e.g., "PP184643")
            pin_number = None
            h4_link = item.select_one("h4 a")
            if h4_link:
                pin_number = h4_link.get_text(strip=True)

            # Pin name from .tbPinsTitle span
            name = None
            title_span = item.select_one("span.tbPinsTitle")
            if title_span:
                name = title_span.get("title") or title_span.get_text(strip=True)

            if not name:
                return None

            return Pin(
                name=name,
                pin_number=pin_number,
                image_url=image_url,
                source=self.source_name,
                source_url=detail_url,
            )
        except Exception as e:
            logger.debug(f"Failed to parse card: {e}")
            return None

    def _parse_detail_page(self, html: str, url: str) -> Optional[Pin]:
        """Parse a PinPics pin detail page."""
        soup = BeautifulSoup(html, "lxml")
        try:
            name = None
            pin_number = None
            series = None
            year = None
            edition_size = None
            image_url = None

            # Extract pin number from URL
            match = re.search(r"/pin/(\d+)", url)
            if match:
                pin_number = f"PP{match.group(1)}"

            # Title
            title_el = soup.find("h1")
            if title_el:
                name = title_el.get_text(strip=True)
            if not name:
                title_tag = soup.find("title")
                if title_tag:
                    name = title_tag.get_text(strip=True).split(" - ")[0].strip()

            # Pin image
            for img in soup.find_all("img"):
                src = img.get("src", "")
                if "/uploads/pins/" in src:
                    image_url = src
                    break

            # Parse metadata fields
            text = soup.get_text(" ", strip=True)

            edition_match = re.search(r"Edition[:\s]*([\w\s\d,]+?)(?:\s{2,}|Year|Origin|Price|$)", text)
            if edition_match:
                edition_size = edition_match.group(1).strip()[:50]

            year_match = re.search(r"Year of Release[:\s]*(\d{4})", text)
            if year_match:
                year = year_match.group(1)

            origin_match = re.search(r"Origin[:\s]*([\w\s]+?)(?:\s{2,}|Edition|Year|Price|$)", text)
            if origin_match:
                series = origin_match.group(1).strip()[:80]

            if not name:
                return None

            return Pin(
                name=name,
                pin_number=pin_number,
                series=series,
                year=year,
                edition_size=edition_size,
                image_url=image_url,
                source=self.source_name,
                source_url=url,
            )
        except Exception as e:
            logger.error(f"Failed to parse detail page {url}: {e}")
            return None
