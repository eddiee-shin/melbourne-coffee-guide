#!/usr/bin/env python3
"""Fix cafe suburbs by looking up the best locality from Google Places.

This version reads and updates rows in Supabase instead of Google Sheets.
"""

from __future__ import annotations

import argparse
import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

from supabase_rest import fetch_rows, update_row

load_dotenv()

DEFAULT_TABLE = "cafes"
DEFAULT_KEY_FIELD = "id"
DEFAULT_SLEEP_SECONDS = 1.0
DEFAULT_PLACES_API_KEY_ENV = "PLACES_API_KEY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fix cafe suburbs and save them to Supabase.")
    parser.add_argument("--supabase-url", default=os.getenv("SUPABASE_URL"), help="Supabase project URL")
    parser.add_argument(
        "--supabase-key",
        default=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY"),
        help="Supabase key (service role preferred for server-side updates)",
    )
    parser.add_argument("--table", default=DEFAULT_TABLE, help="Supabase table name")
    parser.add_argument("--key-field", default=DEFAULT_KEY_FIELD, help="Row key used for updates, usually id or slug")
    parser.add_argument("--places-api-key", default=os.getenv(DEFAULT_PLACES_API_KEY_ENV), help="Google Places API key")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_SECONDS, help="Sleep seconds between Places calls")
    parser.add_argument("--dry-run", action="store_true", help="Print planned updates without writing to Supabase")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N rows")
    return parser.parse_args()


def get_correct_suburb(cafe_name: str, cafe_address: str, places_api_key: str) -> str | None:
    search_url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": places_api_key,
        "X-Goog-FieldMask": "places.addressComponents",
    }
    payload = {
        "textQuery": f"{cafe_name} {cafe_address} Melbourne",
        "languageCode": "en",
    }

    response = requests.post(search_url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()

    places = data.get("places", [])
    if not places:
        return None

    components = places[0].get("addressComponents", [])
    locality = None
    sublocality = None

    for comp in components:
        types = comp.get("types", [])
        if "locality" in types:
            locality = comp.get("shortText", "")
        if "sublocality" in types or "sublocality_level_1" in types:
            sublocality = comp.get("shortText", "")

    result = sublocality if sublocality else locality
    if result and result.lower() == "melbourne":
        return "CBD"
    return result


def fetch_cafes_for_suburb_fix(supabase_url: str, supabase_key: str, table: str) -> list[dict[str, Any]]:
    return fetch_rows(
        supabase_url,
        supabase_key,
        table,
        "id,slug,name,location,suburb",
        order="name.asc",
    )


def main() -> None:
    args = parse_args()

    if not args.places_api_key:
        raise SystemExit(f"Missing API key. Set {DEFAULT_PLACES_API_KEY_ENV} or pass --places-api-key.")
    if not args.supabase_url or not args.supabase_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) are required.")

    cafes = fetch_cafes_for_suburb_fix(args.supabase_url, args.supabase_key, args.table)
    if args.limit and args.limit > 0:
        cafes = cafes[: args.limit]

    updated = 0
    skipped = 0
    missing = 0

    for index, cafe in enumerate(cafes, start=1):
        cafe_name = cafe.get("name")
        cafe_address = cafe.get("location") or cafe.get("suburb") or ""
        current_suburb = (cafe.get("suburb") or "").strip()
        row_key = cafe.get(args.key_field)
        slug = cafe.get("slug") or cafe_name or "<unknown>"

        if not cafe_name:
            print(f"[{index}/{len(cafes)}] Skipping row with missing name: {cafe}")
            missing += 1
            continue
        if row_key in {None, ""}:
            print(f"[{index}/{len(cafes)}] Skipping '{cafe_name}' ({slug}): missing {args.key_field}")
            missing += 1
            continue

        print(f"[{index}/{len(cafes)}] Finding correct suburb for '{cafe_name}' ({slug})...")
        new_suburb = get_correct_suburb(cafe_name, cafe_address, args.places_api_key)

        if not new_suburb:
            print(f"  -> No exact location component found on Google Maps for '{cafe_name}'.")
            missing += 1
            time.sleep(args.sleep)
            continue

        if new_suburb == current_suburb:
            print(f"  -> Suburb already correct: '{current_suburb}'")
            skipped += 1
            time.sleep(args.sleep)
            continue

        if args.dry_run:
            print(f"  -> Dry-run: would update suburb '{current_suburb}' -> '{new_suburb}'")
        else:
            update_row(args.supabase_url, args.supabase_key, args.table, args.key_field, row_key, {"suburb": new_suburb})
            print(f"  -> Updated suburb: '{current_suburb}' -> '{new_suburb}'")
        updated += 1
        time.sleep(args.sleep)

    print()
    print(f"Migration complete. Updated {updated} cafes.")
    print(f"Skipped with existing correct suburb: {skipped}")
    print(f"Missing or unresolved rows: {missing}")


if __name__ == "__main__":
    main()
