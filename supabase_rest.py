from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import requests


def trim_slash(value: str) -> str:
    return value[:-1] if value.endswith("/") else value


def supabase_headers(supabase_key: str, *, content_type: bool = False, prefer: str | None = None) -> dict[str, str]:
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Accept": "application/json",
    }
    if content_type:
        headers["Content-Type"] = "application/json"
    if prefer:
        headers["Prefer"] = prefer
    return headers


def fetch_rows(
    supabase_url: str,
    supabase_key: str,
    table: str,
    select: str,
    *,
    order: str | None = None,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    params = [f"select={select}"]
    if filters:
        for field, expr in filters.items():
            params.append(f"{quote(field)}={expr}")
    if order:
        params.append(f"order={order}")
    endpoint = f"{trim_slash(supabase_url)}/rest/v1/{quote(table)}?{'&'.join(params)}"
    response = requests.get(endpoint, headers=supabase_headers(supabase_key), timeout=30)
    response.raise_for_status()
    return response.json()


def update_row(
    supabase_url: str,
    supabase_key: str,
    table: str,
    key_field: str,
    key_value: Any,
    payload: dict[str, Any],
) -> None:
    endpoint = f"{trim_slash(supabase_url)}/rest/v1/{quote(table)}?{quote(key_field)}=eq.{quote(str(key_value))}"
    response = requests.patch(
        endpoint,
        headers=supabase_headers(supabase_key, content_type=True, prefer="return=minimal"),
        data=json.dumps(payload, ensure_ascii=False),
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(
            f"Failed to update {table} where {key_field}={key_value}: {response.status_code} {response.text}"
        )
