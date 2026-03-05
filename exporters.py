import csv
import json
from typing import List

from models import Pin


def save_json(pins: List[Pin], filepath: str) -> None:
    data = [pin.to_dict() for pin in pins]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(pins)} pin(s) to {filepath}")


def save_csv(pins: List[Pin], filepath: str) -> None:
    if not pins:
        print(f"No pins to save to {filepath}")
        return

    fieldnames = list(pins[0].to_dict().keys())
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for pin in pins:
            writer.writerow(pin.to_dict())
    print(f"Saved {len(pins)} pin(s) to {filepath}")


def save_research_csv(summary_dict: dict, active_listings: list, sold_listings: list, filepath: str) -> None:
    """Write price research data to CSV with summary header and detail rows."""
    fieldnames = [
        "Type", "Title", "Price", "Shipping", "Condition",
        "Seller", "Date", "eBay URL", "Image URL",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        # Summary section
        f.write(f"Price Research: {summary_dict.get('query', '')}\n")
        f.write(f"Active: {summary_dict.get('active_count', 0)} listings")
        if summary_dict.get("active_avg"):
            f.write(f" | Avg ${summary_dict['active_avg']:.2f}")
            f.write(f" | Low ${summary_dict['active_low']:.2f}")
            f.write(f" | High ${summary_dict['active_high']:.2f}")
        f.write("\n")
        f.write(f"Sold (last 90 days): {summary_dict.get('sold_count', 0)} listings")
        if summary_dict.get("sold_avg"):
            f.write(f" | Avg ${summary_dict['sold_avg']:.2f}")
            f.write(f" | Low ${summary_dict['sold_low']:.2f}")
            f.write(f" | High ${summary_dict['sold_high']:.2f}")
        f.write("\n\n")

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for listing in active_listings:
            writer.writerow({
                "Type": "Active",
                "Title": listing.get("title", ""),
                "Price": listing.get("price", ""),
                "Shipping": listing.get("shipping_cost", ""),
                "Condition": listing.get("condition", ""),
                "Seller": listing.get("seller_name", ""),
                "Date": listing.get("end_date", ""),
                "eBay URL": listing.get("ebay_url", ""),
                "Image URL": listing.get("image_url", ""),
            })

        for listing in sold_listings:
            writer.writerow({
                "Type": "Sold",
                "Title": listing.get("title", ""),
                "Price": listing.get("price", ""),
                "Shipping": listing.get("shipping_cost", ""),
                "Condition": listing.get("condition", ""),
                "Seller": listing.get("seller_name", ""),
                "Date": listing.get("sold_date", ""),
                "eBay URL": listing.get("ebay_url", ""),
                "Image URL": listing.get("image_url", ""),
            })
