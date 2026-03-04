import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Pin
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class PinTradingDBScraper(BaseScraper):
    source_name = "PinTradingDB"
    base_url = "https://www.pintradingdb.com"

    def search(self, query: str, limit: int = 20) -> List[Pin]:
        """Search PinTradingDB by keyword using AJAX endpoint."""
        url = f"{self.base_url}/ajaxPinList.php"
        html = self.fetch(url, params={
            "searchString": query,
            "pinPage": "1",
            "sortBy": "releaseDate",
            "sortOrder": "desc",
        })

        if not html:
            # Fallback to the main page
            html = self.fetch(
                f"{self.base_url}/pinList.php",
                params={"searchString": query, "pinPage": "1"},
            )

        if not html:
            logger.warning("PinTradingDB search returned no response")
            return []

        return self._parse_search_results(html, limit)

    def lookup(self, pin_number: str, limit: int = 20) -> List[Pin]:
        """Look up a pin by number on PinTradingDB."""
        # Try direct detail page
        url = f"{self.base_url}/pin/{pin_number}"
        html = self.fetch(url)

        if html:
            pin = self._parse_detail_page(html, url)
            if pin:
                return [pin]

        # Fall back to text search with the number
        return self.search(pin_number, limit)

    def _parse_search_results(self, html: str, limit: int) -> List[Pin]:
        soup = BeautifulSoup(html, "lxml")
        pins = []
        seen = set()

        # PinTradingDB results: <a href="pin/{id}"> with <img> and <strong> for edition
        for a in soup.find_all("a", href=True):
            href = a["href"]

            # Match pin detail links: "pin/12345" or "/pin/12345"
            if not re.search(r"(?:^|/)pin/(\d+)$", href):
                continue

            full_url = urljoin(self.base_url + "/", href)
            if full_url in seen:
                continue
            seen.add(full_url)

            pin = self._parse_result_link(a, full_url)
            if pin:
                pins.append(pin)
                if len(pins) >= limit:
                    break

        return pins

    def _parse_result_link(self, a_tag, detail_url: str) -> Optional[Pin]:
        try:
            # Extract pin number from URL
            match = re.search(r"/pin/(\d+)", detail_url)
            pin_number = match.group(1) if match else None

            # Image: <img src="https://www.ptdb.co/storedImages/{id}_thumb.jpg">
            img = a_tag.find("img")
            image_url = None
            alt_text = None
            if img:
                if img.get("src"):
                    image_url = img["src"]
                alt_text = img.get("alt", "") or img.get("title", "")

            # Edition from <strong> tag (e.g., "OE", "LE 3750", "LR")
            strong = a_tag.find("strong")
            edition_size = strong.get_text(strip=True) if strong else None

            # Name: full text minus the edition badge
            full_text = a_tag.get_text(" ", strip=True)
            name = full_text
            if edition_size and edition_size in name:
                name = name.replace(edition_size, "").strip()

            # If name is empty, try alt text from image
            if not name and alt_text:
                # Alt text format: "{pin_id} - {Pin Name}"
                if " - " in alt_text:
                    name = alt_text.split(" - ", 1)[1].strip()
                else:
                    name = alt_text.strip()

            if not name:
                return None

            return Pin(
                name=name,
                pin_number=pin_number,
                edition_size=edition_size,
                image_url=image_url,
                source=self.source_name,
                source_url=detail_url,
            )
        except Exception as e:
            logger.debug(f"Failed to parse result link: {e}")
            return None

    def _parse_detail_page(self, html: str, url: str) -> Optional[Pin]:
        """Parse a PinTradingDB pin detail page."""
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
                pin_number = match.group(1)

            # Title
            title_el = soup.find("h1")
            if title_el:
                name = title_el.get_text(strip=True)
            if not name:
                title_tag = soup.find("title")
                if title_tag:
                    name = title_tag.get_text(strip=True).split("|")[0].strip()

            # Find pin image from ptdb.co
            for img in soup.find_all("img"):
                src = img.get("src", "")
                if "ptdb.co" in src or "storedImages" in src:
                    image_url = src
                    break

            # Parse table rows for metadata
            for row in soup.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)
                    if "edition" in label:
                        edition_size = value
                    elif "release" in label and "date" in label:
                        year = value
                    elif "origin" in label:
                        series = value
                    elif "series" in label:
                        series = value

            # Also try text-based extraction as fallback
            text = soup.get_text(" ", strip=True)
            if not edition_size:
                ed_match = re.search(r"(LE\s*\d[\d,]*|Open Edition|Limited Release)", text, re.I)
                if ed_match:
                    edition_size = ed_match.group(1)

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
