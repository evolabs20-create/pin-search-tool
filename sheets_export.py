"""Google Sheets export for price research data."""

import os

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False


def export_research(summary: dict, active: list, sold: list, spreadsheet_name: str = None) -> dict:
    """Export research data to Google Sheets.

    Returns dict with 'url' on success or 'error' on failure.
    """
    if not GSPREAD_AVAILABLE:
        return {"error": "Google Sheets libraries not installed. Run: pip install gspread google-auth"}

    creds_path = os.environ.get("GOOGLE_SHEETS_CREDENTIALS", "service_account.json")
    if not os.path.exists(creds_path):
        return {"error": f"Google Sheets credentials not found at {creds_path}. See .env.example for setup."}

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_file(creds_path, scopes=scopes)
        gc = gspread.authorize(credentials)

        if not spreadsheet_name:
            spreadsheet_name = f"Pin Research: {summary.get('query', 'Unknown')}"

        sh = gc.create(spreadsheet_name)

        # --- Summary tab ---
        ws_summary = sh.sheet1
        ws_summary.update_title("Summary")
        summary_data = [
            ["Query", summary.get("query", "")],
            [""],
            ["", "Active", "Sold"],
            ["Count", summary.get("active_count", 0), summary.get("sold_count", 0)],
            ["Low", summary.get("active_low", "N/A"), summary.get("sold_low", "N/A")],
            ["High", summary.get("active_high", "N/A"), summary.get("sold_high", "N/A")],
            ["Average", summary.get("active_avg", "N/A"), summary.get("sold_avg", "N/A")],
            [""],
            ["Last Sold Date", summary.get("last_sold_date", "N/A")],
            ["Cheapest Active", summary.get("cheapest_active_url", "N/A")],
            ["Most Recent Sold", summary.get("most_recent_sold_url", "N/A")],
            [""],
            ["Note: Sold data covers the last ~90 days (eBay Finding API limitation)"],
        ]
        ws_summary.update(range_name="A1", values=summary_data)

        # --- Details tab ---
        ws_details = sh.add_worksheet(title="Details", rows=len(active) + len(sold) + 2, cols=9)
        headers = ["Type", "Title", "Price", "Shipping", "Condition", "Seller", "Date", "eBay URL", "Image URL"]
        rows = [headers]

        for listing in active:
            rows.append([
                "Active",
                listing.get("title", ""),
                listing.get("price", ""),
                listing.get("shipping_cost", ""),
                listing.get("condition", ""),
                listing.get("seller_name", ""),
                listing.get("end_date", ""),
                listing.get("ebay_url", ""),
                listing.get("image_url", ""),
            ])

        for listing in sold:
            rows.append([
                "Sold",
                listing.get("title", ""),
                listing.get("price", ""),
                listing.get("shipping_cost", ""),
                listing.get("condition", ""),
                listing.get("seller_name", ""),
                listing.get("sold_date", ""),
                listing.get("ebay_url", ""),
                listing.get("image_url", ""),
            ])

        ws_details.update(range_name="A1", values=rows)

        # Share as public read
        sh.share(None, perm_type="anyone", role="reader")

        return {"url": sh.url}

    except Exception as e:
        return {"error": f"Google Sheets export failed: {str(e)}"}
