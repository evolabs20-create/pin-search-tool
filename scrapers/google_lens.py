import base64
import logging
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin, quote

from bs4 import BeautifulSoup

from models import Pin
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class GoogleLensScraper(BaseScraper):
    """Reverse image search via Google Lens to identify Disney pins."""

    source_name = "GoogleLens"
    base_url = "https://lens.google.com"

    def search(self, query: str, limit: int = 20) -> List[Pin]:
        """Not used — use search_by_image instead."""
        raise NotImplementedError("Use search_by_image() for Google Lens")

    def lookup(self, pin_number: str, limit: int = 20) -> List[Pin]:
        """Not used — use search_by_image instead."""
        raise NotImplementedError("Use search_by_image() for Google Lens")

    def search_by_image(self, image_path: str, limit: int = 10) -> List[dict]:
        """
        Search Google Lens with a local image file.
        Returns a list of dicts with keys: title, url, thumbnail_url
        These are candidate matches to cross-reference with pin databases.
        """
        path = Path(image_path)
        if not path.exists():
            logger.error(f"Image file not found: {image_path}")
            return []

        # Upload image to Google Lens
        results = self._upload_image(path, limit)
        return results

    def _upload_image(self, image_path: Path, limit: int) -> List[dict]:
        """Upload image to Google Lens and parse visual matches."""
        self._rate_limit()

        try:
            # Read image as multipart upload
            mime = self._guess_mime(image_path)
            with open(image_path, "rb") as f:
                image_data = f.read()

            # Google Lens upload endpoint
            upload_url = "https://lens.google.com/v3/upload"
            resp = self.session.post(
                upload_url,
                files={"encoded_image": (image_path.name, image_data, mime)},
                timeout=self.timeout,
                allow_redirects=True,
            )
            self._last_request_time = __import__("time").time()

            if resp.status_code != 200:
                logger.error(f"Google Lens upload failed: HTTP {resp.status_code}")
                # Try fallback URL-based approach
                return self._search_via_url_method(image_path, limit)

            return self._parse_lens_results(resp.text, limit)

        except Exception as e:
            logger.error(f"Google Lens upload error: {e}")
            return self._search_via_url_method(image_path, limit)

    def _search_via_url_method(self, image_path: Path, limit: int) -> List[dict]:
        """Fallback: encode image as base64 data URI for Google search-by-image."""
        try:
            # Use the older Google reverse image search
            with open(image_path, "rb") as f:
                image_data = f.read()

            b64 = base64.b64encode(image_data).decode()
            mime = self._guess_mime(image_path)

            url = "https://www.google.com/searchbyimage/upload"
            resp = self.session.post(
                url,
                files={"encoded_image": (image_path.name, image_data, mime)},
                data={"image_content": ""},
                timeout=self.timeout,
                allow_redirects=True,
            )
            self._last_request_time = __import__("time").time()

            if resp.status_code != 200:
                logger.error(f"Google reverse image search failed: HTTP {resp.status_code}")
                return []

            return self._parse_google_results(resp.text, limit)

        except Exception as e:
            logger.error(f"Google reverse image search error: {e}")
            return []

    def _parse_lens_results(self, html: str, limit: int) -> List[dict]:
        """Parse Google Lens visual match results."""
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Google Lens shows visual matches in various containers
        # Look for result cards with titles and URLs
        for item in soup.select("div[data-action-url], div.G19kAf, div.Vd9M6, a.islib"):
            title = ""
            url = ""
            thumbnail = ""

            # Extract title
            title_el = item.find(["h3", "span", "div"], class_=re.compile(r"title|name", re.I))
            if title_el:
                title = title_el.get_text(strip=True)
            elif item.get_text(strip=True):
                title = item.get_text(strip=True)[:200]

            # Extract URL
            a_tag = item.find("a", href=True) if item.name != "a" else item
            if a_tag and a_tag.get("href"):
                url = a_tag["href"]
                if url.startswith("/"):
                    url = f"https://www.google.com{url}"

            # Extract thumbnail
            img = item.find("img")
            if img and img.get("src"):
                thumbnail = img["src"]

            if title or url:
                results.append({
                    "title": title,
                    "url": url,
                    "thumbnail_url": thumbnail,
                })

            if len(results) >= limit:
                break

        # Broader fallback: any links mentioning "pin" in text or URL
        if not results:
            results = self._extract_pin_links(soup, limit)

        return results

    def _parse_google_results(self, html: str, limit: int) -> List[dict]:
        """Parse standard Google search results page."""
        soup = BeautifulSoup(html, "html.parser")
        results = []

        for g in soup.select("div.g, div.tF2Cxc"):
            title_el = g.find("h3")
            link_el = g.find("a", href=True)

            if title_el and link_el:
                results.append({
                    "title": title_el.get_text(strip=True),
                    "url": link_el["href"],
                    "thumbnail_url": "",
                })

            if len(results) >= limit:
                break

        if not results:
            results = self._extract_pin_links(soup, limit)

        return results

    def _extract_pin_links(self, soup: BeautifulSoup, limit: int) -> List[dict]:
        """Extract any links that mention pins."""
        results = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)

            if href in seen or not text:
                continue
            seen.add(href)

            # Filter for pin-related results
            combined = (text + " " + href).lower()
            if any(kw in combined for kw in ["pin", "disney", "pinpics", "pintradingdb"]):
                results.append({
                    "title": text[:200],
                    "url": href,
                    "thumbnail_url": "",
                })

            if len(results) >= limit:
                break

        return results

    @staticmethod
    def extract_pin_candidates(results: List[dict]) -> List[str]:
        """
        From Google Lens results, extract likely pin numbers or search terms
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
                # Clean up the title for use as a search query
                clean = re.sub(r'[^\w\s]', ' ', title).strip()
                if clean and clean not in seen:
                    seen.add(clean)
                    candidates.append(clean)

        return candidates

    @staticmethod
    def build_identification(results: List[dict]) -> dict:
        """Build a summary identification dict from Google Lens results."""
        titles = [r["title"] for r in results[:5] if r.get("title")]
        thumbnail = next((r["thumbnail_url"] for r in results if r.get("thumbnail_url")), "")
        description = titles[0] if titles else "No visual matches found"
        return {
            "source": "Google Lens",
            "description": description,
            "top_matches": titles[:5],
            "thumbnail": thumbnail,
        }

    @staticmethod
    def _guess_mime(path: Path) -> str:
        ext = path.suffix.lower()
        return {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }.get(ext, "image/jpeg")
