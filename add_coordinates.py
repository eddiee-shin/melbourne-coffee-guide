#!/usr/bin/env python3
"""Enrich Melbourne Coffee Guide cafes with coordinates.

This version replaces Google Sheets cell writes with Supabase row updates.
It keeps the Google Places lookup logic, but saves results into the database.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()

DEFAULT_TABLE = "cafes"
DEFAULT_API_KEY_ENV = "PLACES_API_KEY"
DEFAULT_SLEEP_SECONDS = 1.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich cafe rows with lat/lng and save them to Supabase.")
    parser.add_argument("--supabase-url", default=os.getenv("SUPABASE_URL"), help="Supabase project URL")
    parser.add_argument(
        "--supabase-key",
        default=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY"),
        help="Supabase key (service role preferred for server-side updates)",
    )
    parser.add_argument("--places-api-key", default=os.getenv(DEFAULT_API_KEY_ENV), help="Google Places API key")
    parser.add_argument("--table", default=DEFAULT_TABLE, help="Supabase table name")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_SECONDS, help="Sleep seconds between Places calls")
    parser.add_argument("--dry-run", action="store_true", help="Print planned updates without writing to Supabase")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N rows")
    return parser.parse_args()


def get_coordinates(cafe_name: str, cafe_address: str, places_api_key: str) -> tuple[float | None, float | None]:
    search_url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": places_api_key,
        "X-Goog-FieldMask": "places.location",
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
        return None, None

    location = places[0].get("location", {})
    lat = location.get("latitude")
    lng = location.get("longitude")
    return lat, lng


def fetch_cafes(supabase_url: str, supabase_key: str, table: str) -> list[dict[str, Any]]:
    endpoint = f"{trim_slash(supabase_url)}/rest/v1/{quote(table)}?select=id,slug,name,location,suburb,lat,lng&order=name.asc"
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


def update_coordinates(supabase_url: str, supabase_key: str, table: str, cafe_id: str, lat: float, lng: float) -> None:
    endpoint = f"{trim_slash(supabase_url)}/rest/v1/{quote(table)}?id=eq.{quote(str(cafe_id))}"
    response = requests.patch(
        endpoint,
        headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        data=json.dumps({"lat": lat, "lng": lng}, ensure_ascii=False),
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"Failed to update cafe {cafe_id}: {response.status_code} {response.text}")


def main() -> None:
    args = parse_args()

    if not args.places_api_key:
        raise SystemExit(f"Missing API key. Set {DEFAULT_API_KEY_ENV} or pass --places-api-key.")
    if not args.supabase_url or not args.supabase_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) are required.")

    cafes = fetch_cafes(args.supabase_url, args.supabase_key, args.table)
    if args.limit and args.limit > 0:
        cafes = cafes[:args.limit]

    updated = 0
    skipped = 0
    missing = 0

    for index, cafe in enumerate(cafes, start=1):
        cafe_name = cafe.get("name")
        cafe_address = cafe.get("suburb") or cafe.get("location") or ""
        cafe_id = cafe.get("id")
        slug = cafe.get("slug") or cafe_name

        current_lat = cafe.get("lat")
        current_lng = cafe.get("lng")
        if is_present(current_lat) and is_present(current_lng):
            print(f"[{index}/{len(cafes)}] Skipping '{cafe_name}' ({slug}): coordinates already exist.")
            skipped += 1
            continue

        if not cafe_name or not cafe_id:
            print(f"[{index}/{len(cafes)}] Skipping row with missing id/name: {cafe}")
            missing += 1
            continue

        print(f"[{index}/{len(cafes)}] Finding coordinates for '{cafe_name}' ({slug})...")
        lat, lng = get_coordinates(cafe_name, cafe_address, args.places_api_key)

        if lat is None or lng is None:
            print(f"  -> No exact location found on Google Maps for '{cafe_name}'.")
            missing += 1
            time.sleep(args.sleep)
            continue

        if args.dry_run:
            print(f"  -> Dry-run: would save coordinates {lat}, {lng}")
        else:
            update_coordinates(args.supabase_url, args.supabase_key, args.table, cafe_id, lat, lng)
            print(f"  -> Saved coordinates {lat}, {lng}")
        updated += 1
        time.sleep(args.sleep)

    print()
    print(f"Migration complete. Added coordinates for {updated} cafes.")
    print(f"Skipped with existing coordinates: {skipped}")
    print(f"Missing or unresolved rows: {missing}")


def is_present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def trim_slash(value: str) -> str:
    return value[:-1] if value.endswith("/") else value


if __name__ == "__main__":
    main()
