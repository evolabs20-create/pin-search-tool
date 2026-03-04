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
