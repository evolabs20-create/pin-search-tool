import logging
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Pin
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class PinTradingDBScraper(BaseScraper):
    source_name = "PinTradingDB"
    base_url = "https://pintradingdb.com"

    def search(self, query: str, limit: int = 20) -> List[Pin]:
        """Search PinTradingDB by keyword."""
        url = f"{self.base_url}/search"
        html = self.fetch(url, params={"q": query})

        # Fallback: try POST-based search
        if not html:
            html = self.post(f"{self.base_url}/search", data={"search": query})

        if not html:
            logger.warning("PinTradingDB search returned no response")
            return []

        return self._parse_search_results(html, limit)

    def lookup(self, pin_number: str, limit: int = 20) -> List[Pin]:
        """Look up a pin by number on PinTradingDB."""
        # Try direct number search
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

        # Try common result container patterns
        items = (
            soup.select(".pin-card")
            or soup.select(".pin-item")
            or soup.select(".search-result")
            or soup.select(".thumbnail")
        )

        for item in items[:limit]:
            pin = self._parse_card(item)
            if pin:
                pins.append(pin)

        # Fallback: look for links to pin detail pages
        if not pins:
            pins = self._parse_links_fallback(soup, limit)

        return pins

    def _parse_card(self, item) -> Optional[Pin]:
        try:
            name = None
            pin_number = None
            edition_size = None
            image_url = None
            detail_url = None

            # Extract link
            a = item.find("a", href=True)
            if a:
                detail_url = urljoin(self.base_url, a["href"])
                if not name:
                    name = a.get_text(strip=True)

            # Title from heading or specific class
            title_el = item.find(["h2", "h3", "h4"]) or item.select_one(".pin-title, .title")
            if title_el:
                name = title_el.get_text(strip=True)

            # Image
            img = item.find("img")
            if img and img.get("src"):
                image_url = urljoin(self.base_url, img["src"])

            # Try to extract pin number from text
            text = item.get_text(" ", strip=True)
            for part in text.split():
                if part.isdigit() and len(part) >= 3:
                    pin_number = part
                    break

            # Edition info
            for span in item.find_all(["span", "div", "p"]):
                span_text = span.get_text(strip=True).lower()
                if "edition" in span_text or "le " in span_text:
                    edition_size = span.get_text(strip=True)
                    break

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
            logger.debug(f"Failed to parse card: {e}")
            return None

    def _parse_links_fallback(self, soup: BeautifulSoup, limit: int) -> List[Pin]:
        pins = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/pin/" not in href:
                continue
            full_url = urljoin(self.base_url, href)
            if full_url in seen:
                continue
            seen.add(full_url)

            name = a.get_text(strip=True)
            if not name:
                continue

            pins.append(Pin(
                name=name,
                source=self.source_name,
                source_url=full_url,
            ))
            if len(pins) >= limit:
                break

        return pins

    def _parse_detail_page(self, html: str, url: str) -> Optional[Pin]:
        soup = BeautifulSoup(html, "lxml")
        try:
            name = None
            pin_number = None
            series = None
            year = None
            edition_size = None
            image_url = None

            title_el = soup.find("h1") or soup.find("title")
            if title_el:
                name = title_el.get_text(strip=True)

            # Parse detail fields
            for row in soup.select("table tr, .detail-row, .info-row, dl dt"):
                if row.name == "tr":
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)
                        self._assign_field(label, value, locals())
                elif row.name == "dt":
                    dd = row.find_next_sibling("dd")
                    if dd:
                        label = row.get_text(strip=True).lower()
                        value = dd.get_text(strip=True)
                        self._assign_field(label, value, locals())

            # Look for labeled spans/divs
            for el in soup.find_all(["span", "div", "p"]):
                text = el.get_text(strip=True).lower()
                if "pin #" in text or "pin number" in text:
                    pin_number = pin_number or text.split(":")[-1].strip().split()[-1]
                elif "edition" in text:
                    edition_size = edition_size or el.get_text(strip=True)
                elif "series" in text or "collection" in text:
                    series = series or text.split(":")[-1].strip()

            # Image
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
                source_url=url,
            )
        except Exception as e:
            logger.error(f"Failed to parse detail page {url}: {e}")
            return None

    @staticmethod
    def _assign_field(label: str, value: str, local_vars: dict) -> None:
        if "number" in label or "pin #" in label:
            local_vars["pin_number"] = local_vars.get("pin_number") or value
        elif "series" in label or "collection" in label:
            local_vars["series"] = local_vars.get("series") or value
        elif "year" in label or "date" in label:
            local_vars["year"] = local_vars.get("year") or value
        elif "edition" in label:
            local_vars["edition_size"] = local_vars.get("edition_size") or value
