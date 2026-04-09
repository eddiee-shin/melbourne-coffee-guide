#!/usr/bin/env python3
"""Export/import Melbourne Coffee Guide cafe data to Supabase.

Modes:
- dry-run (default): print normalized rows and summary only
- csv: write normalized CSV
- sql: write a SQL upsert script
- rest: upsert rows directly into Supabase via REST

This replaces the old Google Sheets sync flow.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

DEFAULT_TABLE = "cafes"
DEFAULT_INPUT = Path(__file__).resolve().parent / "data.json"
DEFAULT_BATCH_SIZE = 100


@dataclass
class Config:
    input_path: Path = DEFAULT_INPUT
    mode: str = "dry-run"
    table: str = DEFAULT_TABLE
    batch_size: int = DEFAULT_BATCH_SIZE
    output_path: Path | None = None
    supabase_url: str | None = None
    supabase_key: str | None = None


def parse_args(argv: list[str]) -> Config:
    cfg = Config()
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in {"--input", "-i"}:
            i += 1
            cfg.input_path = Path(argv[i]).expanduser().resolve()
        elif arg in {"--mode", "-m"}:
            i += 1
            cfg.mode = argv[i].lower()
        elif arg in {"--table", "-t"}:
            i += 1
            cfg.table = argv[i]
        elif arg in {"--batch-size", "--batchSize"}:
            i += 1
            cfg.batch_size = int(argv[i])
        elif arg in {"--output", "-o"}:
            i += 1
            cfg.output_path = Path(argv[i]).expanduser().resolve()
        elif arg == "--supabase-url":
            i += 1
            cfg.supabase_url = argv[i]
        elif arg == "--supabase-key":
            i += 1
            cfg.supabase_key = argv[i]
        elif arg in {"--help", "-h"}:
            print_help()
            raise SystemExit(0)
        else:
            raise SystemExit(f"Unknown argument: {arg}")
        i += 1
    return cfg


def print_help() -> None:
    print(
        """Usage:
  python fetch_data.py [--mode dry-run|csv|sql|rest] [--input data.json] [--output file]

Modes:
  dry-run   Print summary + sample rows (default)
  csv       Write normalized CSV to stdout or --output
  sql       Write INSERT ... ON CONFLICT upsert SQL to stdout or --output
  rest      Upsert directly into Supabase REST API

Environment variables for rest mode:
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY (preferred for server-side use)
  SUPABASE_ANON_KEY (fallback only if your RLS allows inserts)
""".strip()
    )


def main() -> None:
    cfg = parse_args(sys.argv[1:])
    if not cfg.input_path.exists():
        raise SystemExit(f"Input file not found: {cfg.input_path}")

    source = json.loads(cfg.input_path.read_text(encoding="utf-8"))
    if not isinstance(source, list):
        raise SystemExit(f"Expected {cfg.input_path} to contain a JSON array.")

    cafes = [normalize_cafe(row) for row in source]
    duplicates = find_duplicates([row["slug"] for row in cafes])

    if duplicates:
        print(f"Warning: duplicate slugs found: {', '.join(duplicates)}", file=sys.stderr)

    if cfg.mode == "dry-run":
        print(
            json.dumps(
                {
                    "input": str(cfg.input_path),
                    "rows": len(cafes),
                    "unique_slugs": len({row["slug"] for row in cafes}),
                    "sample": cafes[: min(3, len(cafes))],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if cfg.mode == "csv":
        csv_text = to_csv(cafes)
        if cfg.output_path:
            cfg.output_path.write_text(csv_text, encoding="utf-8")
            print(f"Wrote {len(cafes)} cafe rows to {cfg.output_path}")
        else:
            sys.stdout.write(csv_text)
        return

    if cfg.mode == "sql":
        sql_text = to_sql_upsert(cafes, cfg.table)
        if cfg.output_path:
            cfg.output_path.write_text(sql_text, encoding="utf-8")
            print(f"Wrote SQL upsert script for {len(cafes)} rows to {cfg.output_path}")
        else:
            sys.stdout.write(sql_text)
        return

    if cfg.mode == "rest":
        supabase_url = cfg.supabase_url or os.getenv("SUPABASE_URL")
        supabase_key = cfg.supabase_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        if not supabase_url or not supabase_key:
            raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) are required for rest mode.")
        rest_upsert(cafes, cfg.table, supabase_url, supabase_key, cfg.batch_size)
        return

    raise SystemExit(f"Unknown mode: {cfg.mode}. Use dry-run, csv, sql, or rest.")


def normalize_cafe(row: dict[str, Any]) -> dict[str, Any]:
    name = required_text(row.get("name"), "name")
    one_liner = required_text(row.get("one_liner", row.get("oneLiner")), "one_liner")
    description = required_text(row.get("desc", row.get("description")), "desc")
    atmosphere = normalize_text_list(row.get("atmosphere"))
    tags = normalize_text_list(row.get("tags"), delimiter="|")

    return {
        "slug": slugify(name),
        "name": name,
        "location": required_text(row.get("location"), "location"),
        "suburb": required_text(row.get("suburb"), "suburb"),
        "active": bool(row.get("active", True)),
        "spectrum": to_float(row.get("spectrum"), "spectrum"),
        "price": to_int(row.get("price"), "price"),
        "atmosphere": "|".join(atmosphere),
        "description": description,
        "one_liner": one_liner,
        "tags": "|".join(tags),
        "image": optional_text(row.get("image")),
        "image_url": optional_text(row.get("image_url")),
        "image_path": optional_text(row.get("image_path")),
        "rating": to_float(row.get("rating"), "rating"),
        "reviews": to_int(row.get("reviews"), "reviews"),
        "lat": optional_float(row.get("lat")),
        "lng": optional_float(row.get("lng")),
        "signature": optional_text(row.get("signature")),
        "last_scraped_at": optional_text(row.get("last_scraped_at")),
    }


def rest_upsert(rows: list[dict[str, Any]], table: str, supabase_url: str, supabase_key: str, batch_size: int) -> None:
    endpoint = f"{trim_slash(supabase_url)}/rest/v1/{quote(table)}?on_conflict=slug"
    total_batches = (len(rows) + batch_size - 1) // batch_size

    session = requests.Session()
    for batch_index, start in enumerate(range(0, len(rows), batch_size), start=1):
        batch = rows[start:start + batch_size]
        response = session.post(
            endpoint,
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            data=json.dumps(batch, ensure_ascii=False),
            timeout=60,
        )
        if not response.ok:
            raise SystemExit(
                f"Supabase REST import failed for batch {batch_index}/{total_batches}: {response.status_code} {response.text}"
            )
        print(f"Imported batch {batch_index}/{total_batches} ({len(batch)} rows)")

    print(f"Done. Upserted {len(rows)} cafe rows into {table}.")


def to_csv(rows: list[dict[str, Any]]) -> str:
    headers = [
        "slug", "name", "location", "suburb", "spectrum", "price", "atmosphere", "description",
        "one_liner", "tags", "image", "rating", "reviews", "lat", "lng", "signature",
    ]
    output = [",".join(headers)]
    for row in rows:
        output.append(",".join(csv_cell(row.get(header)) for header in headers))
    return "\n".join(output) + "\n"


def to_sql_upsert(rows: list[dict[str, Any]], table: str) -> str:
    values_sql = []
    for row in rows:
        values_sql.append(
            "(" + ", ".join([
                sql_string(row.get("slug")),
                sql_string(row.get("name")),
                sql_string(row.get("location")),
                sql_string(row.get("suburb")),
                sql_boolean(row.get("active", True)),
                sql_number(row.get("spectrum")),
                sql_number(row.get("price")),
                sql_string(row.get("atmosphere")),
                sql_string(row.get("description")),
                sql_string(row.get("one_liner")),
                sql_string(row.get("tags")),
                sql_string_or_null(row.get("image")),
                sql_string_or_null(row.get("image_url")),
                sql_string_or_null(row.get("image_path")),
                sql_number(row.get("rating")),
                sql_number(row.get("reviews")),
                sql_number_or_null(row.get("lat")),
                sql_number_or_null(row.get("lng")),
                sql_string_or_null(row.get("signature")),
                sql_string_or_null(row.get("last_scraped_at")),
            ]) + ")"
        )

    joined_values = ',\n'.join(values_sql)
    return f"""insert into public.{table} (
  slug, name, location, suburb, spectrum, price, atmosphere, description, one_liner, tags, image, rating, reviews, lat, lng, signature
) values
{joined_values}
on conflict (slug) do update set
  name = excluded.name,
  location = excluded.location,
  suburb = excluded.suburb,
  spectrum = excluded.spectrum,
  price = excluded.price,
  atmosphere = excluded.atmosphere,
  description = excluded.description,
  one_liner = excluded.one_liner,
  tags = excluded.tags,
  image = excluded.image,
  rating = excluded.rating,
  reviews = excluded.reviews,
  lat = excluded.lat,
  lng = excluded.lng,
  signature = excluded.signature,
  updated_at = timezone('utc', now());
"""


def slugify(value: str) -> str:
    value = str(value)
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = value.strip().lower()
    return re.sub(r"[\s_-]+", "-", value)


def required_text(value: Any, field: str) -> str:
    text = optional_text(value)
    if not text:
        raise SystemExit(f"Missing required field: {field}")
    return text


def optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def normalize_text_list(value: Any, delimiter: str = "|") -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = str(value).split(delimiter)
    return [str(item).strip() for item in items if str(item).strip()]


def to_float(value: Any, field: str) -> float:
    try:
        num = float(value)
    except Exception as exc:
        raise SystemExit(f"Invalid numeric value for {field}: {value}") from exc
    return num


def optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def to_int(value: Any, field: str) -> int:
    try:
        return int(float(value))
    except Exception as exc:
        raise SystemExit(f"Invalid integer value for {field}: {value}") from exc


def csv_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if any(ch in text for ch in [",", '"', "\n"]):
        return '"' + text.replace('"', '""') + '"'
    return text


def sql_string(value: Any) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def sql_boolean(value: Any) -> str:
    return "true" if bool(value) else "false"


def sql_string_or_null(value: Any) -> str:
    return "null" if value is None else sql_string(value)


def sql_number(value: Any) -> str:
    return str(value) if value is not None else "null"


def sql_number_or_null(value: Any) -> str:
    return "null" if value is None else str(value)


def trim_slash(value: str) -> str:
    return value[:-1] if value.endswith("/") else value


def find_duplicates(values: list[str]) -> list[str]:
    seen = set()
    dupes = []
    for value in values:
        if value in seen and value not in dupes:
            dupes.append(value)
        seen.add(value)
    return dupes


if __name__ == "__main__":
    main()
