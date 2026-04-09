#!/usr/bin/env python3
"""Enrich Melbourne Coffee Guide cafes with image URLs.

This version keeps the Google Places image lookup logic but writes results
straight to the Supabase cafes table instead of Google Sheets.
"""

from __future__ import annotations

import argparse
import os
import time
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()

DEFAULT_TABLE = "cafes"
DEFAULT_SLEEP_SECONDS = 1.0
DEFAULT_API_KEY_ENV = "PLACES_API_KEY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enrich cafe rows with image URLs and save them to Supabase."
    )
    parser.add_argument("--supabase-url", default=os.getenv("SUPABASE_URL"), help="Supabase project URL")
    parser.add_argument(
        "--supabase-key",
        default=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY"),
        help="Supabase key (service role preferred for server-side updates)",
    )
    parser.add_argument(
        "--places-api-key",
        default=os.getenv(DEFAULT_API_KEY_ENV),
        help="Google Places API key",
    )
    parser.add_argument("--table", default=DEFAULT_TABLE, help="Supabase table name")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_SECONDS, help="Sleep seconds between Places calls")
    parser.add_argument("--dry-run", action="store_true", help="Print planned updates without writing to Supabase")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N rows")
    return parser.parse_args()


def trim_slash(value: str) -> str:
    return value[:-1] if value.endswith("/") else value


def is_present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def fetch_cafes(supabase_url: str, supabase_key: str, table: str) -> list[dict[str, Any]]:
    endpoint = f"{trim_slash(supabase_url)}/rest/v1/{quote(table)}?select=id,slug,name,image&order=name.asc"
    response = requests.get(
        endpoint,
        headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Accept": "application/json",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def update_image(supabase_url: str, supabase_key: str, table: str, cafe_id: str, image_url: str) -> None:
    endpoint = f"{trim_slash(supabase_url)}/rest/v1/{quote(table)}?id=eq.{quote(str(cafe_id))}"
    response = requests.patch(
        endpoint,
        headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json={"image": image_url},
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"Failed to update cafe {cafe_id}: {response.status_code} {response.text}")


def get_photo_reference(cafe_name: str, places_api_key: str) -> str | None:
    search_url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": places_api_key,
        "X-Goog-FieldMask": "places.photos",
    }
    payload = {
        "textQuery": f"{cafe_name} specialty coffee Melbourne",
        "languageCode": "en",
    }

    response = requests.post(search_url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()

    places = data.get("places", [])
    if not places:
        return None

    photos = places[0].get("photos", [])
    if not photos:
        return None

    return photos[0].get("name", "") or None


def build_photo_url(photo_reference: str, places_api_key: str) -> str:
    if not photo_reference:
        return ""
    return f"https://places.googleapis.com/v1/{photo_reference}/media?key={places_api_key}&maxHeightPx=400&maxWidthPx=400"


def main() -> None:
    args = parse_args()

    if not args.places_api_key:
        raise SystemExit(f"Missing API key. Set {DEFAULT_API_KEY_ENV} or pass --places-api-key.")
    if not args.supabase_url or not args.supabase_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) are required.")

    cafes = fetch_cafes(args.supabase_url, args.supabase_key, args.table)
    if args.limit and args.limit > 0:
        cafes = cafes[: args.limit]

    updated = 0
    skipped = 0
    missing = 0

    for index, cafe in enumerate(cafes, start=1):
        cafe_name = cafe.get("name")
        cafe_id = cafe.get("id")
        slug = cafe.get("slug") or cafe_name or "<unknown>"
        current_image = cafe.get("image", "")

        if not cafe_name or not cafe_id:
            print(f"[{index}/{len(cafes)}] Skipping row with missing id/name: {cafe}")
            missing += 1
            continue

        if is_present(current_image) and str(current_image).startswith("http"):
            print(f"[{index}/{len(cafes)}] Skipping '{cafe_name}' ({slug}): image already exists.")
            skipped += 1
            continue

        print(f"[{index}/{len(cafes)}] Finding image for '{cafe_name}' ({slug})...")
        try:
            photo_ref = get_photo_reference(cafe_name, args.places_api_key)
        except requests.RequestException as exc:
            print(f"  -> Places lookup failed for '{cafe_name}': {exc}")
            missing += 1
            time.sleep(args.sleep)
            continue

        if not photo_ref:
            print(f"  -> No photo found on Google Maps for '{cafe_name}'.")
            missing += 1
            time.sleep(args.sleep)
            continue

        new_url = build_photo_url(photo_ref, args.places_api_key)
        if not new_url:
            print(f"  -> Could not build a photo URL for '{cafe_name}'.")
            missing += 1
            time.sleep(args.sleep)
            continue

        if args.dry_run:
            print(f"  -> Dry-run: would save image URL {new_url}")
        else:
            update_image(args.supabase_url, args.supabase_key, args.table, cafe_id, new_url)
            print(f"  -> Saved image URL for '{cafe_name}'")
        updated += 1
        time.sleep(args.sleep)

    print()
    print(f"Migration complete. Added image URLs for {updated} cafes.")
    print(f"Skipped with existing images: {skipped}")
    print(f"Missing or unresolved rows: {missing}")


if __name__ == "__main__":
    main()
