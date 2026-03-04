#!/usr/bin/env python3
"""Disney Pin Search — Flask Web Application."""

import json
import os
import tempfile

from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

from models import Pin
from scrapers import PinPicsScraper, PinTradingDBScraper
from exporters import save_csv
from pin_identifier import get_search_queries
import database

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

SCRAPERS = {
    "pinpics": PinPicsScraper,
    "pintradingdb": PinTradingDBScraper,
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
    return jsonify({"results": result, "count": len(result)})


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
    return jsonify({"results": result, "count": len(result)})


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
        # Step 1: Claude Vision identifies the pin
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return jsonify({"error": "ANTHROPIC_API_KEY not configured on server"}), 500

        queries, identification = get_search_queries(filepath, api_key)

        if not queries:
            return jsonify({
                "error": "Could not identify the pin from the image",
                "identification": identification,
            }), 200

        # Step 2: Search pin databases with Claude's identified queries
        scrapers = _get_scrapers(source)
        all_pins = []
        seen = set()
        for query in queries[:3]:
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

        result = [p.to_dict() for p in all_pins]
        _mark_collection(result)
        database.add_search_history("image", identification.get("description", filename), len(result))
        return jsonify({
            "results": result,
            "count": len(result),
            "identification": identification,
            "queries_used": queries[:3],
        })
    except Exception as e:
        app.logger.error(f"Image search error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


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
