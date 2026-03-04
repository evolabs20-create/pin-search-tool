import logging
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Pin
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class PinPicsScraper(BaseScraper):
    source_name = "PinPics"
    base_url = "https://www.pinpics.com"

    def search(self, query: str, limit: int = 20) -> List[Pin]:
        """Search PinPics by keyword/description."""
        url = f"{self.base_url}/search.php"
        html = self.fetch(url, params={"keysearch": query})
        if not html:
            logger.warning("PinPics search returned no response")
            return []
        return self._parse_search_results(html, limit)

    def lookup(self, pin_number: str, limit: int = 20) -> List[Pin]:
        """Look up a specific pin by number on PinPics."""
        url = f"{self.base_url}/search.php"
        html = self.fetch(url, params={"keysearch": pin_number, "searchtype": "pinnumber"})
        if not html:
            logger.warning("PinPics lookup returned no response")
            return []
        return self._parse_search_results(html, limit)

    def _parse_search_results(self, html: str, limit: int) -> List[Pin]:
        soup = BeautifulSoup(html, "lxml")
        pins = []

        # Try multiple selectors to handle site layout variations
        rows = soup.select("table.searchresults tr") or soup.select("table tr")

        for row in rows[:limit + 5]:  # grab extra to account for header rows
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            pin = self._parse_row(cells)
            if pin:
                pins.append(pin)
                if len(pins) >= limit:
                    break

        # Fallback: try parsing links that look like pin detail pages
        if not pins:
            pins = self._parse_links_fallback(soup, limit)

        return pins

    def _parse_row(self, cells) -> Optional[Pin]:
        try:
            # Extract pin number and name from cells
            text_parts = [c.get_text(strip=True) for c in cells]

            # Look for a link to a detail page
            link = None
            for cell in cells:
                a = cell.find("a", href=True)
                if a and ("pinID" in a["href"] or "pin" in a["href"].lower()):
                    link = urljoin(self.base_url, a["href"])
                    break

            # Try to find an image
            img_url = None
            for cell in cells:
                img = cell.find("img")
                if img and img.get("src"):
                    img_url = urljoin(self.base_url, img["src"])
                    break

            # Build pin from available data
            name = ""
            pin_number = None
            series = None

            for part in text_parts:
                if not part:
                    continue
                # If it looks like a number, treat as pin number
                if part.isdigit() and not pin_number:
                    pin_number = part
                elif not name:
                    name = part
                elif not series:
                    series = part

            if not name:
                return None

            return Pin(
                name=name,
                pin_number=pin_number,
                series=series,
                image_url=img_url,
                source=self.source_name,
                source_url=link,
            )
        except Exception as e:
            logger.debug(f"Failed to parse row: {e}")
            return None

    def _parse_links_fallback(self, soup: BeautifulSoup, limit: int) -> List[Pin]:
        """Fallback parser: find all pin detail links."""
        pins = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "pinID" not in href and "pin_id" not in href.lower():
                continue
            if href in seen:
                continue
            seen.add(href)

            name = a.get_text(strip=True)
            if not name:
                continue

            pins.append(Pin(
                name=name,
                source=self.source_name,
                source_url=urljoin(self.base_url, href),
            ))
            if len(pins) >= limit:
                break

        return pins

    def get_detail(self, pin_url: str) -> Optional[Pin]:
        """Fetch full details from a pin's detail page."""
        html = self.fetch(pin_url)
        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")
        try:
            name = None
            pin_number = None
            series = None
            year = None
            edition_size = None
            image_url = None

            # Look for title
            title_el = soup.find("h1") or soup.find("title")
            if title_el:
                name = title_el.get_text(strip=True)

            # Parse info table/fields
            for row in soup.select("table tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)
                    if "pin" in label and "number" in label:
                        pin_number = value
                    elif "series" in label or "collection" in label:
                        series = value
                    elif "year" in label or "date" in label:
                        year = value
                    elif "edition" in label:
                        edition_size = value

            # Find main image
            for img in soup.find_all("img"):
                src = img.get("src", "")
                if "pin" in src.lower() or "image" in src.lower():
                    image_url = urljoin(self.base_url, src)
                    break

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
                source_url=pin_url,
            )
        except Exception as e:
            logger.error(f"Failed to parse detail page {pin_url}: {e}")
            return None
