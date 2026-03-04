# Disney Pin Search Tool

CLI tool to search Disney pin databases (PinPics, PinTradingDB) by description, pin number, or image. Results are exported to JSON and CSV.

## Install

```bash
cd pin-search-tool
pip install -r requirements.txt
```

## Usage

### Search by keyword
```bash
python main.py search "Mickey Mouse"
python main.py search "Haunted Mansion" --source pinpics --limit 10
```

### Look up by pin number
```bash
python main.py lookup 12345
python main.py lookup 12345 --source pintradingdb
```

### Search by image
```bash
python main.py image photo_of_pin.jpg
python main.py image pin_scan.png --source pinpics
```

This uploads the image to Google Lens, identifies the pin from visual matches, extracts pin numbers/names, then cross-references with PinPics/PinTradingDB to get full details.

### Options
| Flag | Description | Default |
|------|-------------|---------|
| `--source` | `pinpics`, `pintradingdb`, or `all` | `all` |
| `--output` / `-o` | Output filename prefix | `results` |
| `--limit` / `-l` | Max results per source | `20` |
| `--delay` | Seconds between requests | `1.5` |
| `--verbose` / `-v` | Show debug logging | off |

### Output
Results are saved as `<output>.json` and `<output>.csv` in the current directory.

## Adding a New Source

1. Create `scrapers/newsource.py` with a class that extends `BaseScraper`
2. Implement `search()` and `lookup()` methods
3. Register it in `scrapers/__init__.py` and `main.py`'s `SCRAPERS` dict

The `BaseScraper` base class provides session management, User-Agent rotation, rate limiting, and retry logic with exponential backoff.
