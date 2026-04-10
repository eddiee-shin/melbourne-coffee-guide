#!/usr/bin/env python3
"""Bulk scrape Melbourne coffee cafes and persist them to Supabase.

This keeps the existing Google Maps search + Gemini analysis flow, but replaces
Google Sheets writes with Supabase REST upserts or SQL output.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(path: str | Path | None = None) -> None:
        if not path:
            return
        dotenv_path = Path(path)
        if not dotenv_path.exists():
            return
        for raw_line in dotenv_path.read_text(encoding='utf-8').splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

from google import genai
from google.genai import types

from fetch_data import rest_upsert, slugify, to_sql_upsert

load_dotenv()

# Support both the old and current env var names.
PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("PLACES_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_TABLE = "cafes"
DEFAULT_QUERY = "best specialty coffee in Melbourne CBD"
DEFAULT_BATCH_SIZE = 25
DEFAULT_MAX_NEW = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search cafes, analyze them with Gemini, and upsert into Supabase.")
    parser.add_argument("query", nargs="?", default=DEFAULT_QUERY, help="Google Maps text query to search")
    parser.add_argument("--mode", choices=("rest", "sql", "dry-run"), default="rest", help="Persistence mode")
    parser.add_argument("--dry-run", action="store_true", help="Print planned writes without persisting")
    parser.add_argument("--table", default=DEFAULT_TABLE, help="Supabase table name")
    parser.add_argument("--supabase-url", default=os.getenv("SUPABASE_URL"), help="Supabase project URL")
    parser.add_argument(
        "--supabase-key",
        default=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY"),
        help="Supabase key (service role preferred for writes)",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Supabase REST batch size")
    parser.add_argument("--output", type=Path, help="Write SQL output to this file when using --mode sql")
    parser.add_argument(
        "--max-new",
        type=int,
        default=DEFAULT_MAX_NEW,
        help="Maximum number of new cafes to add in a single run (0 = unlimited)",
    )
    parser.add_argument(
        "--refresh-all",
        action="store_true",
        help="Refresh ratings and review counts for all existing cafes in Supabase",
    )
    return parser.parse_args()


def build_photo_url(photo_reference: str | None) -> str:
    if not photo_reference:
        return ""
    return f"https://places.googleapis.com/v1/{photo_reference}/media?key={PLACES_API_KEY}&maxHeightPx=400&maxWidthPx=400"


def fetch_existing_cafes(supabase_url: str | None, supabase_key: str | None, table: str) -> list[dict[str, Any]]:
    if not supabase_url or not supabase_key:
        return []

    endpoint = f"{trim_slash(supabase_url)}/rest/v1/{table}?select=*&order=name.asc"
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
    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected Supabase response when fetching cafes: {data}")
    return data


def search_cafes(query: str, exact_match: bool = False) -> list[dict[str, Any]]:
    print(f"\nSearching Google Maps for: '{query}'...")

    search_url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": PLACES_API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.rating,places.userRatingCount,places.formattedAddress,places.reviews,places.photos,places.addressComponents,places.location",
    }
    payload = {
        "textQuery": query,
        "languageCode": "ko",
    }

    response = requests.post(search_url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise RuntimeError(data["error"].get("message", "Unknown Google Places error"))

    places = data.get("places", [])
    if not places:
        print("No cafes found.")
        return []

    results: list[dict[str, Any]] = []
    for place in places:
        name = place.get("displayName", {}).get("text", "Unknown")

        raw_reviews = place.get("reviews", [])
        review_texts = []
        for review in raw_reviews:
            text = review.get("text", {}).get("text", "")
            if text:
                review_texts.append(text)

        photos = place.get("photos", [])
        photo_ref = photos[0].get("name", "") if photos else ""

        components = place.get("addressComponents", [])
        locality = None
        sublocality = None
        for comp in components:
            comp_types = comp.get("types", [])
            if "locality" in comp_types:
                locality = comp.get("shortText", "")
            if "sublocality" in comp_types or "sublocality_level_1" in comp_types:
                sublocality = comp.get("shortText", "")

        suburb = sublocality if sublocality else locality
        if suburb and suburb.lower() == "melbourne":
            suburb = "CBD"
        if not suburb:
            formatted_address = place.get("formattedAddress", "")
            suburb = formatted_address.split(",")[0].split(" ")[-1] if "," in formatted_address else "Melbourne"

        location = place.get("location", {})
        lat = location.get("latitude")
        lng = location.get("longitude")

        user_rating_count = place.get("userRatingCount", 0)
        if user_rating_count < 50:
            print(f"  -> Skipping '{name}' (Low review count: {user_rating_count})")
            continue

        if not review_texts:
            print(f"  -> Skipping '{name}' (No reviews available for AI analysis)")
            continue

        results.append(
            {
                "name": name,
                "address": place.get("formattedAddress", ""),
                "suburb": suburb,
                "lat": lat,
                "lng": lng,
                "rating": place.get("rating", 0),
                "reviews": user_rating_count,
                "review_texts": review_texts,
                "photo_reference": photo_ref,
            }
        )

    print(f"-> Found {len(results)} candidate cafes with reviews from Google Maps.")
    return results


def analyze_cafe_with_ai(cafe_data: dict[str, Any], existing_names: list[str]) -> dict[str, Any] | None:
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY not found in .env. Skipping AI analysis.")
        return None

    print(f"\n[AI] Analyzing reviews for '{cafe_data['name']}'...")
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""
    Analyze the following cafe based on its name, address, and Google reviews.
    Cafe Name: {cafe_data['name']}
    Address: {cafe_data['address']}

    Here is a list of cafes ALREADY in our database (some might be in English, some in Korean):
    {json.dumps(existing_names, ensure_ascii=False)}

    Reviews:
    {json.dumps(cafe_data['review_texts'], ensure_ascii=False, indent=2)}

    Please output a JSON object with EXACTLY these keys:
    - "isDuplicate": boolean (true/false). Set to true ONLY if this cafe conceptually already exists in the provided list. Be extremely smart about English/Korean translations (e.g. "듁스 커피 로스터스" is the same as "Dukes Coffee Roasters").
    - "location": string. Strictly map the address to ONE of these exactly: ["CBD", "North Melbourne", "South Melbourne", "Fitzroy/Collingwood", "Brunswick", "Carlton", "Others"].
    - "spectrum": integer from 1 to 5. 1=Very Fruity/Acidic, 3=Balanced, 5=Very Nutty/Chocolatey/Comforting.
    - "price": integer from 1 to 5. (1=Cheap, 5=Very Expensive).
    - "atmosphere": Array of 1 to 2 strings from this list exactly: ["modern", "cozy", "unique", "lively"]
    - "desc": A 1-2 sentence description in Korean about the vibe and coffee taste.
    - "oneLiner": A catchy, short one-liner in Korean (subtitle style).
    - "signature": A short string (1-3 words in Korean or English) representing the cafe's signature COFFEE or ESPRESSO DRINK based on the reviews, e.g., "Magic", "Raspberry Candy Filter", "라떼", "필터 커피". If unclear, return "스페셜티 커피". CRITICAL: MUST BE A COFFEE/BEVERAGE, NOT FOOD.
    - "tags": Array of 2 strings. The 1st string MUST be exactly one of: ["Acidity ⭐⭐⭐⭐⭐", "Acidity ⭐⭐⭐⭐", "Balance ⭐⭐⭐⭐⭐", "Balance ⭐⭐⭐", "Nutty ⭐⭐⭐⭐⭐", "Nutty ⭐⭐⭐⭐"] matching the spectrum. The 2nd string is a short English catchy word (e.g. "Signature", "Hipster").

    Return ONLY JSON.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    try:
        result = json.loads(response.text)

        if result.get("isDuplicate", False):
            print(
                f"  -> AI DETECTED DUPLICATE: '{cafe_data['name']}' is already in the database under a different name/language. Skipping."
            )
            return None

        atmosphere = normalize_text_list(result.get("atmosphere"))
        if not atmosphere:
            atmosphere = ["cozy"]

        tags = normalize_text_list(result.get("tags"))

        merged = {
            "slug": slugify(cafe_data["name"]),
            "name": cafe_data["name"],
            "location": result.get("location", "Others"),
            "suburb": cafe_data.get("suburb", "Melbourne"),
            "active": True,
            "spectrum": result.get("spectrum", 3),
            "price": result.get("price", 3),
            "atmosphere": "|".join(atmosphere),
            "description": result.get("desc", ""),
            "one_liner": result.get("oneLiner", ""),
            "tags": "|".join(tags),
            "image": build_photo_url(cafe_data.get("photo_reference")),
            "image_url": build_photo_url(cafe_data.get("photo_reference")),
            "image_path": None,
            "rating": cafe_data.get("rating", 0),
            "reviews": cafe_data.get("reviews", 0),
            "lat": cafe_data.get("lat"),
            "lng": cafe_data.get("lng"),
            "signature": result.get("signature", "스페셜티 커피"),
            "last_scraped_at": None,
        }
        return merged
    except Exception as exc:
        print(f"Error parsing Gemini response: {exc}")
        return None


def normalize_text_list(value: Any, delimiter: str = "|") -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = str(value).split(delimiter)
    return [str(item).strip() for item in items if str(item).strip()]


def persist_cafes(
    cafes: list[dict[str, Any]],
    mode: str,
    table: str,
    supabase_url: str | None,
    supabase_key: str | None,
    batch_size: int,
    output_path: Path | None,
) -> None:
    if not cafes:
        print("\nNo new cafes to persist.")
        return

    if mode == "dry-run":
        print("\nDry-run summary:")
        print(json.dumps({"rows": len(cafes), "sample": cafes[: min(3, len(cafes))]}, ensure_ascii=False, indent=2))
        return

    if mode == "sql":
        sql_text = to_sql_upsert(cafes, table)
        if output_path:
            output_path.write_text(sql_text, encoding="utf-8")
            print(f"\nWrote SQL upsert script for {len(cafes)} cafes to {output_path}")
        else:
            sys.stdout.write(sql_text)
        return

    if not supabase_url or not supabase_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) are required for rest mode.")

    rest_upsert(cafes, table, supabase_url, supabase_key, batch_size)


def trim_slash(value: str) -> str:
    return value[:-1] if value.endswith("/") else value


if __name__ == "__main__":
    args = parse_args()
    if args.dry_run:
        args.mode = "dry-run"

    if not PLACES_API_KEY:
        print("ERROR: Missing PLACES_API_KEY in .env file.")
        raise SystemExit(1)
    if not GEMINI_API_KEY:
        print("ERROR: Missing GEMINI_API_KEY in .env file.")
        raise SystemExit(1)
    if genai is None or types is None:
        print("ERROR: Missing google-genai package. Install it in the active Python environment.")
        raise SystemExit(1)

    print("=== Melbourne Coffee Bulk Automation Bot ===")

    existing_names: list[str] = []
    existing_cafes: list[dict[str, Any]] = []
    existing_data_map: dict[str, dict[str, Any]] = {}
    if args.mode != "dry-run" or args.supabase_url or args.supabase_key:
        try:
            existing_cafes = fetch_existing_cafes(args.supabase_url, args.supabase_key, args.table)
            existing_names = [row.get("name", "") for row in existing_cafes if row.get("name")]
            # Map by normalized name for easy lookup
            for row in existing_cafes:
                if row.get("name"):
                    existing_data_map[row["name"].strip().lower()] = row
            print(f"-> Found {len(existing_names)} existing cafes in Supabase.")
        except Exception as exc:
            if args.mode == "dry-run":
                print(f"Warning: could not fetch existing cafes from Supabase: {exc}")
            else:
                print(f"Failed to connect to Supabase: {exc}")
                raise SystemExit(1)

    query = args.query or DEFAULT_QUERY
    try:
        candidates = search_cafes(query)
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)

    added_count = 0
    updated_count = 0
    cafes_to_persist: list[dict[str, Any]] = []
    
    # --- Mode 1: Refresh Stats for All Existing Cafes ---
    if args.refresh_all:
        print(f"\n---> Starting full stats refresh for {len(existing_names)} cafes...")
        for name in existing_names:
            try:
                # Search for the exact cafe name
                found = search_cafes(name, exact_match=True)
                if found:
                    # Find the best match (closest name)
                    best = found[0]
                    existing_row = existing_data_map.get(name.strip().lower(), {})
                    
                    # Create payload preserving all required fields
                    payload = {
                        **existing_row, # Keep all current fields (location, suburb, atmosphere, etc.)
                        "rating": best["rating"],
                        "reviews": best["reviews"],
                        "last_scraped_at": datetime.now(timezone.utc).isoformat()
                    }
                    # Remove DB-internal fields that shouldn't be in upsert
                    for key in ["id", "created_at", "updated_at", "updated_by"]:
                        payload.pop(key, None)
                        
                    cafes_to_persist.append(payload)
                    updated_count += 1
                    print(f"  [REFRESH] '{name}': {best['rating']} ({best['reviews']} reviews)")
                else:
                    print(f"  [SKIP] Could not find '{name}' on Google Maps.")
            except Exception as e:
                print(f"  [ERROR] Failed to refresh '{name}': {e}")
        
        persist_cafes(
            cafes_to_persist,
            args.mode,
            args.table,
            args.supabase_url,
            args.supabase_key,
            args.batch_size,
            args.output,
        )
        print(f"\nDone! Refreshed stats for {updated_count} cafe(s).")
        sys.exit(0)

    # --- Mode 2: Standard Search and Smart Upsert ---
    existing_name_set = {name.strip().lower() for name in existing_names}

    for cafe in candidates:
        cafe_name = cafe.get("name", "")
        cafe_key = cafe_name.strip().lower()
        if cafe_key and cafe_key in existing_name_set:
            print(f"  -> Existing cafe found: '{cafe_name}'. Refreshing stats only.")
            existing_row = existing_data_map.get(cafe_key, {})
            
            # Create payload preserving all required fields
            payload = {
                **existing_row,
                "rating": cafe.get("rating", 0),
                "reviews": cafe.get("reviews", 0),
                "last_scraped_at": datetime.now(timezone.utc).isoformat()
            }
            # Remove DB-internal fields
            for key in ["id", "created_at", "updated_at", "updated_by"]:
                payload.pop(key, None)

            cafes_to_persist.append(payload)
            updated_count += 1
            continue

        analyzed = analyze_cafe_with_ai(cafe, existing_names)
        if analyzed:
            analyzed["last_scraped_at"] = datetime.now(timezone.utc).isoformat()
            cafes_to_persist.append(analyzed)
            added_count += 1
            if analyzed.get("name"):
                existing_names.append(analyzed["name"])
                existing_name_set.add(analyzed["name"].strip().lower())

            if args.max_new and added_count >= args.max_new:
                print(f"\nReached limit of {args.max_new} bulk additions for this run.")
                break

    persist_cafes(
        cafes_to_persist,
        args.mode,
        args.table,
        args.supabase_url,
        args.supabase_key,
        args.batch_size,
        args.output,
    )

    print(f"\nDone! Added {added_count} new and updated {updated_count} existing cafe(s).")
