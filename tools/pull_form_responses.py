#!/usr/bin/env python3
"""
Pull Google Form responses into a local contacts CSV.

Authenticates with Google Sheets API via service account,
reads the "Connect with TELOS" form response spreadsheet,
deduplicates by email (keeps most recent), and exports to CSV.

Setup (one-time):
  1. Google Cloud Console → create a service account
  2. Download JSON key → save as .secrets/google_service_account.json
  3. Share the response Google Sheet with the service account email (read-only)
  4. Set SPREADSHEET_ID below to the response sheet's ID

Usage:
  python3 tools/pull_form_responses.py
"""

import csv
import os
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Google Sheet ID from the form's response spreadsheet URL:
# https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit
SPREADSHEET_ID = "YOUR_SPREADSHEET_ID_HERE"

# Paths (relative to repo root)
REPO_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = REPO_ROOT / ".secrets" / "google_service_account.json"
OUTPUT_DIR = REPO_ROOT / "contacts"
OUTPUT_FILE = OUTPUT_DIR / "telos_interest_directory.csv"

# Expected column headers from the Google Form response sheet
# (Google Forms auto-adds "Timestamp" as column A)
EXPECTED_HEADERS = [
    "Timestamp",
    "Where should we reach you?",
    "What should we call you?",
    "Where do you work? (Organization, university, or independent -- all welcome)",
    "LinkedIn or professional profile URL (helps us understand your background, but not required)",
    "What draws you to AI governance?",
    "How do you see yourself contributing to or benefiting from this work? (Optional -- following along is just as valued)",
]

# Canonical CSV column names
CSV_HEADERS = [
    "timestamp",
    "email",
    "name",
    "organization",
    "profile_url",
    "interest",
    "collaboration",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def check_dependencies():
    """Verify required packages are installed."""
    missing = []
    try:
        import gspread  # noqa: F401
    except ImportError:
        missing.append("gspread")
    try:
        import google.auth  # noqa: F401
    except ImportError:
        missing.append("google-auth")

    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        sys.exit(1)


def load_previous_emails(path: Path) -> set:
    """Load emails from a previous export to calculate new contacts."""
    if not path.exists():
        return set()
    emails = set()
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = row.get("email", "").strip().lower()
            if email:
                emails.add(email)
    return emails


def deduplicate_by_email(rows: list[dict]) -> list[dict]:
    """Keep the most recent response per email address.

    Rows are assumed to be in chronological order (oldest first),
    so later entries overwrite earlier ones.
    """
    seen = OrderedDict()
    for row in rows:
        email = row.get("email", "").strip().lower()
        if email:
            seen[email] = row
    return list(seen.values())


def org_type_breakdown(rows: list[dict]) -> dict[str, int]:
    """Simple breakdown by whether organization field is filled."""
    has_org = sum(1 for r in rows if r.get("organization", "").strip())
    no_org = len(rows) - has_org
    return {"with_organization": has_org, "independent_or_unlisted": no_org}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__.strip())
        sys.exit(0)

    if SPREADSHEET_ID == "YOUR_SPREADSHEET_ID_HERE":
        print("ERROR: Set SPREADSHEET_ID at the top of this script.")
        print("Find it in the Google Sheets URL:")
        print("  https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit")
        sys.exit(1)

    check_dependencies()

    import gspread
    from google.oauth2.service_account import Credentials

    # Authenticate
    if not CREDENTIALS_PATH.exists():
        print(f"ERROR: Service account key not found at {CREDENTIALS_PATH}")
        print("Download it from Google Cloud Console and save it there.")
        sys.exit(1)

    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    credentials = Credentials.from_service_account_file(str(CREDENTIALS_PATH), scopes=scopes)
    client = gspread.authorize(credentials)

    # Open spreadsheet
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"ERROR: Spreadsheet not found (ID: {SPREADSHEET_ID})")
        print("Make sure the sheet is shared with the service account email.")
        sys.exit(1)

    sheet = spreadsheet.sheet1
    all_values = sheet.get_all_values()

    if len(all_values) < 2:
        print("No responses yet.")
        sys.exit(0)

    # Parse rows (skip header row)
    header_row = all_values[0]
    rows = []
    for values in all_values[1:]:
        row = {}
        for i, canonical in enumerate(CSV_HEADERS):
            row[canonical] = values[i].strip() if i < len(values) else ""
        rows.append(row)

    # Load previous state for "new since last pull"
    previous_emails = load_previous_emails(OUTPUT_FILE)

    # Deduplicate
    rows = deduplicate_by_email(rows)

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Write CSV
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    current_emails = {r["email"].strip().lower() for r in rows}
    new_emails = current_emails - previous_emails

    breakdown = org_type_breakdown(rows)

    print(f"\n{'='*50}")
    print(f"  TELOS Interest Directory -- Pull Complete")
    print(f"{'='*50}")
    print(f"  Total contacts:          {len(rows)}")
    print(f"  New since last pull:     {len(new_emails)}")
    print(f"  With organization:       {breakdown['with_organization']}")
    print(f"  Independent/unlisted:    {breakdown['independent_or_unlisted']}")
    print(f"  Output:                  {OUTPUT_FILE}")
    print(f"  Pulled at:               {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
