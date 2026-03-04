#!/usr/bin/env python3
"""Disney Pin Search Tool — search PinPics and PinTradingDB from the command line."""

import argparse
import logging
import sys
from typing import List

from models import Pin
from scrapers import PinPicsScraper, PinTradingDBScraper, GoogleLensScraper
from exporters import save_json, save_csv

SCRAPERS = {
    "pinpics": PinPicsScraper,
    "pintradingdb": PinTradingDBScraper,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search Disney pin databases by description, pin number, or image.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # search subcommand
    search_p = sub.add_parser("search", help="Search by keyword/description")
    search_p.add_argument("query", help="Search terms (e.g. 'Mickey Mouse')")

    # lookup subcommand
    lookup_p = sub.add_parser("lookup", help="Look up by pin number")
    lookup_p.add_argument("pin_number", help="Pin number to look up")

    # image subcommand
    image_p = sub.add_parser("image", help="Search by image (reverse image search)")
    image_p.add_argument("image_path", help="Path to pin image file (jpg, png, etc.)")

    # shared options
    for p in (search_p, lookup_p, image_p):
        p.add_argument(
            "--source",
            choices=["pinpics", "pintradingdb", "all"],
            default="all",
            help="Which pin database to cross-reference (default: all)",
        )
        p.add_argument(
            "--output", "-o",
            default="results",
            help="Output filename prefix (generates .json and .csv)",
        )
        p.add_argument(
            "--limit", "-l",
            type=int,
            default=20,
            help="Max results per source (default: 20)",
        )
        p.add_argument(
            "--delay",
            type=float,
            default=1.5,
            help="Delay between requests in seconds (default: 1.5)",
        )
        p.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Enable verbose logging",
        )

    return parser


def get_scrapers(source: str, delay: float) -> list:
    if source == "all":
        return [cls(delay=delay) for cls in SCRAPERS.values()]
    return [SCRAPERS[source](delay=delay)]


def run_search(args) -> List[Pin]:
    scrapers = get_scrapers(args.source, args.delay)
    all_pins = []

    for scraper in scrapers:
        print(f"Searching {scraper.source_name}...")
        try:
            if args.command == "search":
                pins = scraper.search(args.query, limit=args.limit)
            else:
                pins = scraper.lookup(args.pin_number, limit=args.limit)

            print(f"  Found {len(pins)} result(s) from {scraper.source_name}")
            all_pins.extend(pins)
        except Exception as e:
            logging.error(f"Error querying {scraper.source_name}: {e}")
            print(f"  Error querying {scraper.source_name}: {e}")

    return all_pins


def run_image_search(args) -> List[Pin]:
    """Reverse image search: Google Lens identifies the pin, then cross-references pin DBs."""
    lens = GoogleLensScraper(delay=args.delay)

    print(f"Uploading image to Google Lens: {args.image_path}")
    lens_results = lens.search_by_image(args.image_path, limit=10)

    if not lens_results:
        print("Google Lens returned no results.")
        return []

    print(f"Google Lens found {len(lens_results)} visual match(es):")
    for i, r in enumerate(lens_results, 1):
        print(f"  {i}. {r.get('title', '(no title)')}")
        if r.get("url"):
            print(f"     {r['url']}")

    # Extract pin numbers and search terms from Lens results
    candidates = GoogleLensScraper.extract_pin_candidates(lens_results)
    if not candidates:
        # Use the first result title as a search term
        for r in lens_results:
            title = r.get("title", "").strip()
            if title:
                candidates.append(title)
                break

    if not candidates:
        print("Could not extract pin identifiers from image results.")
        return []

    print(f"\nCross-referencing with pin databases using: {candidates[:3]}")

    # Search pin databases with extracted candidates
    scrapers = get_scrapers(args.source, args.delay)
    all_pins = []
    seen_keys = set()

    for candidate in candidates[:3]:  # limit to top 3 candidates
        for scraper in scrapers:
            print(f"  Querying {scraper.source_name} for '{candidate}'...")
            try:
                # If candidate is purely numeric, do a lookup; otherwise search
                if candidate.isdigit():
                    pins = scraper.lookup(candidate, limit=args.limit)
                else:
                    pins = scraper.search(candidate, limit=args.limit)

                for pin in pins:
                    key = (pin.name, pin.pin_number, pin.source)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_pins.append(pin)

                if pins:
                    print(f"    Found {len(pins)} result(s)")
            except Exception as e:
                logging.error(f"Error querying {scraper.source_name}: {e}")
                print(f"    Error: {e}")

    return all_pins


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(name)s: %(message)s",
    )

    if args.command == "image":
        pins = run_image_search(args)
    else:
        pins = run_search(args)

    if not pins:
        print("No results found.")
        sys.exit(0)

    print(f"\nTotal: {len(pins)} pin(s) found.")

    json_path = f"{args.output}.json"
    csv_path = f"{args.output}.csv"
    save_json(pins, json_path)
    save_csv(pins, csv_path)


if __name__ == "__main__":
    main()
