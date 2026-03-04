from dataclasses import dataclass, field, asdict
from typing import Optional


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
