#!/usr/bin/env python3
"""Fetch Saudi market data after the close; keep the last good snapshot on failures."""
import json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

BASE = "https://api.sahmk.sa/api/v1"
OUT = Path("data/market.json")
KEY = os.environ.get("SAHMK_API_KEY", "").strip()
if not KEY:
    raise SystemExit("Missing SAHMK_API_KEY secret")

def read_old():
    try: return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception: return {}

def api(path, params=None):
    url = BASE + path
    if params: url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"X-API-Key": KEY, "Accept": "application/json", "User-Agent": "SaudiAI-MarketDashboard/1.0"})
    with urllib.request.urlopen(req, timeout=25) as res:
        data = json.loads(res.read().decode("utf-8"))
    if not isinstance(data, dict) or data.get("error"):
        raise RuntimeError(f"Invalid API response: {path}")
    return data

old = read_old()
now = datetime.now(timezone.utc).isoformat(timespec="seconds")
result = dict(old)
result.setdefault("markets", {})
result.setdefault("indices", {})
result.setdefault("companies", {})
result["provider"] = "SAHMK"
result["source_url"] = "https://www.sahmk.sa/developers/docs/stocks"

# Stage 1 — always request both market indices before any individual stock lists.
for market in ("TASI", "NOMU"):
    result["indices"][market] = api("/market/summary/", {"index": market})

# Do not relabel a previous session as today's update on weekends or exchange holidays.
riyadh_today = datetime.now(ZoneInfo("Asia/Riyadh")).date()
for market, summary in result["indices"].items():
    source_stamp = summary.get("timestamp")
    if not source_stamp:
        raise SystemExit(f"Missing source timestamp for {market}; previous snapshot retained")
    parsed_stamp = datetime.fromisoformat(source_stamp.replace("Z", "+00:00"))
    if parsed_stamp.astimezone(ZoneInfo("Asia/Riyadh")).date() != riyadh_today:
        raise SystemExit(f"{market} has no new session data for {riyadh_today}; previous snapshot retained")

# Stage 2 — main-market leaders first: turnover value and volume.
# Stage 3 — then gainers/losers, followed by Nomu in the same priority order.
for market in ("TASI", "NOMU"):
    section = dict(result["markets"].get(market, {}))
    for category, endpoint, key in (
        ("leaders_value", "/market/value/", "stocks"),
        ("leaders_volume", "/market/volume/", "stocks"),
        ("gainers", "/market/gainers/", "gainers"),
        ("losers", "/market/losers/", "losers"),
    ):
        try:
            payload = api(endpoint, {"index": market, "limit": 50})
            section[category] = payload.get(key, [])
            section[category + "_updated_at"] = payload.get("timestamp") or now
        except Exception as exc:
            print(f"WARNING: {market} {category} retained from previous snapshot: {exc}")
            if category not in section:
                section[category] = []
    result["markets"][market] = section

# Directory: all active equities only (not sukuk, ETFs or funds).
for market in ("TASI", "NOMU"):
    try:
        directory = api("/companies/", {"market": market, "limit": 500, "offset": 0})
        rows = directory.get("results", [])
        result["companies"][market] = [
            {"symbol": x.get("symbol"), "name_ar": x.get("name_ar"), "name_en": x.get("name_en"), "market": market}
            for x in rows
            if str(x.get("status", "")).lower() == "active"
            and x.get("security_type") == "Equity"
            and x.get("symbol")
        ]
    except Exception as exc:
        print(f"WARNING: {market} company directory retained from previous snapshot: {exc}")

# Household LPG refill prices: official GASCO price list, including VAT and transport.
result["household_gas"] = {
    "cylinder_11kg_sar": 37.00,
    "cylinder_5kg_sar": 16.82,
    "central_tank_per_liter_sar": 1.69,
    "effective_date": "2026-07-01",
    "includes_vat_and_transport": True,
    "source": "GASCO",
    "source_url": "https://gasco.com.sa/"
}
result["updated_at"] = now
result["timezone"] = "Asia/Riyadh"
OUT.parent.mkdir(parents=True, exist_ok=True)
tmp = OUT.with_suffix(".json.tmp")
tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
tmp.replace(OUT)
print("Market snapshot saved:", OUT)
print("TASI equities:", len(result["companies"].get("TASI", [])))
print("NOMU equities:", len(result["companies"].get("NOMU", [])))
