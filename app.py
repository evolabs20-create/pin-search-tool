#!/usr/bin/env python3
"""Disney Pin Search — Flask Web Application."""

import base64
import json
import os
import re

from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from werkzeug.utils import secure_filename

from models import Pin
from scrapers import eBayScraper
from scrapers import google_lens
from exporters import save_csv
from price_research import research_pin
import database

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB


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
        # Strip existing "Disney pin" prefix to avoid double-prefix
        # since research_pin → eBay scraper already prepends it
        clean = re.sub(r'^disney\s+pin\s+', '', query, flags=re.IGNORECASE).strip()
        return research_pin(clean or query, active_limit=20, sold_limit=20)
    except Exception as e:
        app.logger.error(f"Auto-pricing error for '{query}': {e}")
        return None


# --- Pages ---

@app.route("/")
def index():
    history = database.get_search_history()
    return render_template("index.html", history_json=json.dumps(history))


@app.route("/uploads/<filename>")
def serve_upload(filename):
    """Serve uploaded images so SerpAPI can fetch them via public URL."""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# --- Search APIs ---

@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    limit = request.args.get("limit", 20, type=int)

    if not q:
        return jsonify({"error": "Missing query"}), 400

    try:
        scraper = eBayScraper()
        all_pins = scraper.search(q, limit=limit)
    except Exception as e:
        app.logger.error(f"eBay search error: {e}")
        all_pins = []

    result = [p.to_dict() for p in all_pins]
    _mark_collection(result)
    database.add_search_history("keyword", q, len(result))
    pricing = _get_pricing(q)
    resp = {"results": result, "count": len(result)}
    if pricing:
        resp["pricing"] = pricing
    return jsonify(resp)


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

    limit = request.form.get("limit", 20, type=int)

    try:
        # Step 1: Google Lens via SerpAPI (needs public image URL)
        public_url = request.url_root.rstrip("/") + f"/uploads/{filename}"
        lens_results = google_lens.search_by_image(public_url)
        candidates = google_lens.extract_pin_candidates(lens_results)
        identification = google_lens.build_identification(lens_results)

        queries = candidates[:3] if candidates else []

        # Step 2: Search eBay with identified queries
        all_pins = []
        seen = set()
        if queries:
            scraper = eBayScraper()
            for query in queries:
                try:
                    pins = scraper.search(query, limit=limit)
                    for pin in pins:
                        key = (pin.name, pin.pin_number, pin.source)
                        if key not in seen:
                            seen.add(key)
                            all_pins.append(pin)
                except Exception as e:
                    app.logger.error(f"eBay search error: {e}")

        # Step 3: eBay image search (base64 visual matching)
        ebay_matches = []
        try:
            with open(filepath, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode()
            ebay_scraper = eBayScraper()
            ebay_image_pins = ebay_scraper.search_by_image(image_b64, limit=limit)
            ebay_matches = [p.to_dict() for p in ebay_image_pins]
        except Exception as e:
            app.logger.error(f"eBay image search error: {e}")

        result = [p.to_dict() for p in all_pins]
        _mark_collection(result)
        _mark_collection(ebay_matches)
        database.add_search_history("image", identification.get("description", filename), len(result))

        # Step 4: Auto-pricing using the best query
        pricing = None
        if queries:
            pricing = _get_pricing(queries[0])

        resp = {
            "results": result,
            "count": len(result),
            "identification": identification,
            "queries_used": queries,
            "ebay_matches": ebay_matches,
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
