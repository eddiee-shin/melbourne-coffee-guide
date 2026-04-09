#!/usr/bin/env python3
"""Enrich cafe rows with signature drinks and save them to Supabase.

This version reads and updates rows in Supabase instead of Google Sheets.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any

import requests
from dotenv import load_dotenv
from google import genai

from supabase_rest import fetch_rows, update_row

load_dotenv()

DEFAULT_TABLE = "cafes"
DEFAULT_KEY_FIELD = "id"
DEFAULT_PLACES_API_KEY_ENV = "PLACES_API_KEY"
DEFAULT_GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
DEFAULT_SLEEP_SECONDS = 1.0
DEFAULT_FALLBACK_SIGNATURE = "스페셜티 커피"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract signature drinks and save them to Supabase.")
    parser.add_argument("--supabase-url", default=os.getenv("SUPABASE_URL"), help="Supabase project URL")
    parser.add_argument(
        "--supabase-key",
        default=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY"),
        help="Supabase key (service role preferred for server-side updates)",
    )
    parser.add_argument("--table", default=DEFAULT_TABLE, help="Supabase table name")
    parser.add_argument("--key-field", default=DEFAULT_KEY_FIELD, help="Row key used for updates, usually id or slug")
    parser.add_argument("--places-api-key", default=os.getenv(DEFAULT_PLACES_API_KEY_ENV), help="Google Places API key")
    parser.add_argument("--gemini-api-key", default=os.getenv(DEFAULT_GEMINI_API_KEY_ENV), help="Gemini API key")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_SECONDS, help="Sleep seconds between API calls")
    parser.add_argument("--dry-run", action="store_true", help="Print planned updates without writing to Supabase")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N rows")
    return parser.parse_args()


def get_reviews(cafe_name: str, cafe_address: str, places_api_key: str) -> list[str]:
    search_url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": places_api_key,
        "X-Goog-FieldMask": "places.reviews",
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
        return []

    reviews = places[0].get("reviews", [])
    return [rev.get("text", {}).get("text", "") for rev in reviews if rev.get("text")]


def extract_signature(cafe_name: str, review_texts: list[str], gemini_api_key: str) -> str:
    if not gemini_api_key or not review_texts:
        return ""

    client = genai.Client(api_key=gemini_api_key)
    prompt = f"""
Analyze the following cafe reviews and extract the cafe's SIGNATURE COFFEE or COFFEE/ESPRESSO DRINK.
Cafe Name: {cafe_name}
Reviews:
{json.dumps(review_texts, ensure_ascii=False, indent=2)}

Output exactly ONE short string (1-3 words) representing the signature coffee/drink in Korean or English (e.g., "Magic", "Raspberry Candy Filter", "바닐라 라떼", "Filter Coffee", "에스프레소").
Do NOT output JSON. Do NOT add explanation or punctuation. Just the item name. If unclear, output "스페셜티 커피".
CRITICAL: YOU MUST ONLY OUTPUT A COFFEE OR BEVERAGE. DO NOT OUTPUT FOOD ITEMS (e.g., "Hotcakes", "Eggs Benedict", "Pastries"). If the cafe is famous for food, ignore it and find their best coffee.
""".strip()

    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    time.sleep(1)
    return (response.text or "").strip()


def fetch_cafes_for_signature_fix(supabase_url: str, supabase_key: str, table: str) -> list[dict[str, Any]]:
    return fetch_rows(
        supabase_url,
        supabase_key,
        table,
        "id,slug,name,location,suburb,signature",
        order="name.asc",
    )


def main() -> None:
    args = parse_args()

    if not args.places_api_key:
        raise SystemExit(f"Missing API key. Set {DEFAULT_PLACES_API_KEY_ENV} or pass --places-api-key.")
    if not args.gemini_api_key:
        raise SystemExit(f"Missing API key. Set {DEFAULT_GEMINI_API_KEY_ENV} or pass --gemini-api-key.")
    if not args.supabase_url or not args.supabase_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) are required.")

    cafes = fetch_cafes_for_signature_fix(args.supabase_url, args.supabase_key, args.table)
    if args.limit and args.limit > 0:
        cafes = cafes[: args.limit]

    updated = 0
    skipped = 0
    missing = 0

    for index, cafe in enumerate(cafes, start=1):
        cafe_name = cafe.get("name")
        cafe_address = cafe.get("location") or cafe.get("suburb") or ""
        current_signature = (cafe.get("signature") or "").strip()
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

        print(f"[{index}/{len(cafes)}] Analyzing signature for '{cafe_name}' ({slug})...")
        reviews = get_reviews(cafe_name, cafe_address, args.places_api_key)

        if not reviews:
            signature = DEFAULT_FALLBACK_SIGNATURE
            print(f"  -> No reviews found. Defaulting to '{signature}'.")
        else:
            signature = extract_signature(cafe_name, reviews, args.gemini_api_key) or DEFAULT_FALLBACK_SIGNATURE
            print(f"  -> Extracted Signature: {signature}")

        if signature == current_signature:
            print(f"  -> Signature already current: '{current_signature}'")
            skipped += 1
            time.sleep(args.sleep)
            continue

        if args.dry_run:
            print(f"  -> Dry-run: would update signature '{current_signature}' -> '{signature}'")
        else:
            update_row(args.supabase_url, args.supabase_key, args.table, args.key_field, row_key, {"signature": signature})
            print(f"  -> Saved signature: '{signature}'")
        updated += 1
        time.sleep(args.sleep)

    print()
    print(f"Migration complete. Added signatures for {updated} cafes.")
    print(f"Skipped with existing signature: {skipped}")
    print(f"Missing or unresolved rows: {missing}")


if __name__ == "__main__":
    main()
