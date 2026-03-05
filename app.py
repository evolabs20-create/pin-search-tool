#!/usr/bin/env python3
"""Disney Pin Search — Flask Web Application."""

import base64
import json
import os

from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

from models import Pin
from scrapers import PinPicsScraper, PinTradingDBScraper, eBayScraper
from scrapers.google_lens import GoogleLensScraper
from exporters import save_csv, save_research_csv
from price_research import research_pin
from sheets_export import export_research
import database

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

SCRAPERS = {
    "pinpics": PinPicsScraper,
    "pintradingdb": PinTradingDBScraper,
    "ebay": eBayScraper,
}


def _get_scrapers(source: str, delay: float = 1.5):
    if source == "all":
        return [cls(delay=delay) for cls in SCRAPERS.values()]
    return [SCRAPERS[source](delay=delay)]


def _mark_collection(results: list) -> list:
    for pin_dict in results:
        pin_dict["in_collection"] = database.is_in_collection(
            pin_dict.get("name", ""),
            pin_dict.get("pin_number"),
            pin_dict.get("source", ""),
        )
    return results


def _get_pricing(query: str) -> dict | None:
    """Run price research and return pricing dict, or None on failure."""
    try:
        return research_pin(query, active_limit=20, sold_limit=20)
    except Exception as e:
        app.logger.error(f"Auto-pricing error for '{query}': {e}")
        return None


# --- Pages ---

@app.route("/")
def index():
    history = database.get_search_history()
    return render_template("index.html", history_json=json.dumps(history))


# --- Search APIs ---

@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    source = request.args.get("source", "all")
    limit = request.args.get("limit", 20, type=int)

    if not q:
        return jsonify({"error": "Missing query"}), 400

    scrapers = _get_scrapers(source)
    all_pins = []
    for scraper in scrapers:
        try:
            all_pins.extend(scraper.search(q, limit=limit))
        except Exception as e:
            app.logger.error(f"{scraper.source_name}: {e}")

    result = [p.to_dict() for p in all_pins]
    _mark_collection(result)
    database.add_search_history("keyword", q, len(result))
    pricing = _get_pricing(q)
    resp = {"results": result, "count": len(result)}
    if pricing:
        resp["pricing"] = pricing
    return jsonify(resp)


@app.route("/api/lookup")
def api_lookup():
    pin_number = request.args.get("pin_number", "").strip()
    source = request.args.get("source", "all")
    limit = request.args.get("limit", 20, type=int)

    if not pin_number:
        return jsonify({"error": "Missing pin_number"}), 400

    scrapers = _get_scrapers(source)
    all_pins = []
    for scraper in scrapers:
        try:
            all_pins.extend(scraper.lookup(pin_number, limit=limit))
        except Exception as e:
            app.logger.error(f"{scraper.source_name}: {e}")

    result = [p.to_dict() for p in all_pins]
    _mark_collection(result)
    database.add_search_history("lookup", pin_number, len(result))
    pricing = _get_pricing(f"disney pin {pin_number}")
    resp = {"results": result, "count": len(result)}
    if pricing:
        resp["pricing"] = pricing
    return jsonify(resp)


@app.route("/api/ebay-sold")
def api_ebay_sold():
    """Search for sold eBay listings to get price history."""
    q = request.args.get("q", "").strip()
    limit = request.args.get("limit", 20, type=int)

    if not q:
        return jsonify({"error": "Missing query"}), 400

    try:
        scraper = eBayScraper()
        pins = scraper.search_sold(q, limit=limit)
        result = [p.to_dict() for p in pins]
        return jsonify({"results": result, "count": len(result)})
    except Exception as e:
        app.logger.error(f"eBay sold search error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/image-search", methods=["POST"])
def api_image_search():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    source = request.form.get("source", "all")
    limit = request.form.get("limit", 20, type=int)

    try:
        # Step 1: Google Lens identifies the pin
        lens = GoogleLensScraper()
        lens_results = lens.search_by_image(filepath, limit=10)
        candidates = GoogleLensScraper.extract_pin_candidates(lens_results)
        identification = GoogleLensScraper.build_identification(lens_results)

        queries = candidates[:3] if candidates else []

        if not queries:
            return jsonify({
                "error": "Could not identify the pin from the image",
                "identification": identification,
            }), 200

        # Step 2: Search pin databases with Google Lens identified queries
        scrapers = _get_scrapers(source)
        all_pins = []
        seen = set()
        for query in queries:
            for scraper in scrapers:
                try:
                    if query.isdigit():
                        pins = scraper.lookup(query, limit=limit)
                    else:
                        pins = scraper.search(query, limit=limit)
                    for pin in pins:
                        key = (pin.name, pin.pin_number, pin.source)
                        if key not in seen:
                            seen.add(key)
                            all_pins.append(pin)
                except Exception as e:
                    app.logger.error(f"{scraper.source_name} search error: {e}")

        # Step 3: eBay image search (parallel visual matching)
        try:
            with open(filepath, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode()
            ebay_scraper = eBayScraper()
            ebay_image_pins = ebay_scraper.search_by_image(image_b64, limit=limit)
            for pin in ebay_image_pins:
                key = (pin.name, pin.pin_number, pin.source)
                if key not in seen:
                    seen.add(key)
                    all_pins.append(pin)
        except Exception as e:
            app.logger.error(f"eBay image search error: {e}")

        result = [p.to_dict() for p in all_pins]
        _mark_collection(result)
        database.add_search_history("image", identification.get("description", filename), len(result))

        # Auto-pricing using the best query
        pricing = _get_pricing(queries[0])

        resp = {
            "results": result,
            "count": len(result),
            "identification": identification,
            "queries_used": queries,
        }
        if pricing:
            resp["pricing"] = pricing
        return jsonify(resp)
    except Exception as e:
        app.logger.error(f"Image search error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


# --- Price Research APIs ---

@app.route("/api/research")
def api_research():
    """Run price research for a query — returns summary + all listings."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Missing query"}), 400

    active_limit = request.args.get("active_limit", 40, type=int)
    sold_limit = request.args.get("sold_limit", 40, type=int)

    try:
        data = research_pin(q, active_limit=active_limit, sold_limit=sold_limit)
        return jsonify(data)
    except Exception as e:
        app.logger.error(f"Research error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/research/export/csv")
def api_research_export_csv():
    """Download price research results as CSV."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Missing query"}), 400

    active_limit = request.args.get("active_limit", 40, type=int)
    sold_limit = request.args.get("sold_limit", 40, type=int)

    try:
        data = research_pin(q, active_limit=active_limit, sold_limit=sold_limit)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], "research_export.csv")
        save_research_csv(data["summary"], data["active_listings"], data["sold_listings"], filepath)
        return send_file(
            filepath,
            as_attachment=True,
            download_name=f"pin_research_{q.replace(' ', '_')}.csv",
        )
    except Exception as e:
        app.logger.error(f"Research CSV export error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/research/export/sheets", methods=["POST"])
def api_research_export_sheets():
    """Push research data to Google Sheets."""
    body = request.get_json() or {}
    q = body.get("q", "").strip()
    if not q:
        return jsonify({"error": "Missing query"}), 400

    active_limit = body.get("active_limit", 40)
    sold_limit = body.get("sold_limit", 40)

    try:
        data = research_pin(q, active_limit=active_limit, sold_limit=sold_limit)
        result = export_research(
            data["summary"],
            data["active_listings"],
            data["sold_listings"],
        )
        if "error" in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Research Sheets export error: {e}")
        return jsonify({"error": str(e)}), 500


# --- Collection APIs ---

@app.route("/api/collection")
def get_collection():
    return jsonify({"pins": database.get_collection()})


@app.route("/api/collection", methods=["POST"])
def add_to_collection():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Pin data required"}), 400

    pin_dict = {
        "name": data.get("name", ""),
        "pin_number": data.get("pin_number"),
        "series": data.get("series"),
        "year": data.get("year"),
        "edition_size": data.get("edition_size"),
        "image_url": data.get("image_url"),
        "source": data.get("source", ""),
        "source_url": data.get("source_url"),
    }
    row_id = database.add_to_collection(pin_dict)
    return jsonify({"id": row_id, "message": "Pin saved"})


@app.route("/api/collection/<int:pin_id>", methods=["DELETE"])
def remove_from_collection(pin_id):
    if database.remove_from_collection(pin_id):
        return jsonify({"message": "Removed"})
    return jsonify({"error": "Not found"}), 404


@app.route("/api/collection/export")
def export_collection():
    collection = database.get_collection()
    if not collection:
        return jsonify({"error": "Collection is empty"}), 404

    pins = [
        Pin(**{k: v for k, v in item.items() if k in Pin.__dataclass_fields__})
        for item in collection
    ]
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], "collection_export.csv")
    save_csv(pins, filepath)
    return send_file(
        filepath,
        as_attachment=True,
        download_name="disney_pin_collection.csv",
    )


# --- History APIs ---

@app.route("/api/history")
def get_history():
    return jsonify({"history": database.get_search_history()})


@app.route("/api/history", methods=["DELETE"])
def clear_history():
    database.clear_search_history()
    return jsonify({"message": "History cleared"})


# --- Startup ---

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
database.init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
