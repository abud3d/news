#!/usr/bin/env python3
"""Save one end-of-session market snapshot in the repository; retain last good quotes."""
import json, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("data/market.json")
BASES = ["https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"]
SYMBOLS = {"tasi": "^TASI", "brent": "BZ=F", "gold": "GC=F"}

def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def yahoo_quote(symbol):
    path = "/v8/finance/chart/" + urllib.parse.quote(symbol, safe="") + "?range=5d&interval=1d"
    last_error = None
    for base in BASES:
        try:
            req = urllib.request.Request(base + path, headers={
                "User-Agent": "Mozilla/5.0 SaudiAI-MarketSnapshot/1.0",
                "Accept": "application/json"
            })
            with urllib.request.urlopen(req, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            item = payload["chart"]["result"][0]
            closes = [x for x in (item.get("indicators", {}).get("quote", [{}])[0].get("close") or []) if isinstance(x, (int, float))]
            if not closes:
                raise ValueError("No closing prices in provider response")
            price = closes[-1]
            previous = closes[-2] if len(closes) > 1 else item.get("meta", {}).get("chartPreviousClose") or item.get("meta", {}).get("previousClose")
            change = ((price - previous) / previous * 100) if previous else 0
            stamps = item.get("timestamp") or []
            stamp = datetime.fromtimestamp(stamps[-1], timezone.utc).isoformat(timespec="seconds") if stamps else datetime.now(timezone.utc).isoformat(timespec="seconds")
            return {
                "symbol": symbol, "price": price, "change_percent": change,
                "currency": item.get("meta", {}).get("currency", ""),
                "timestamp": stamp, "source": "Yahoo Finance (" + base.split("//")[1] + ")",
                "history": closes
            }
        except Exception as exc:
            last_error = exc
    raise RuntimeError(str(last_error or "Quote unavailable"))

data = read_json(OUT)
data.setdefault("quotes", {})
now = datetime.now(timezone.utc).isoformat(timespec="seconds")
updated = []
for key, symbol in SYMBOLS.items():
    try:
        data["quotes"][key] = yahoo_quote(symbol)
        updated.append(key)
        print("Updated", key, "from", data["quotes"][key]["source"])
    except Exception as exc:
        print("WARNING:", key, "kept previous repository value:", exc)

# Gold conversion is an estimate using the SAR/USD peg; source ounce quote is retained too.
gold = data["quotes"].get("gold")
if gold and isinstance(gold.get("price"), (int, float)):
    ounce_sar = gold["price"] * 3.75
    gram24 = ounce_sar / 31.1034768
    gold["gram24_sar_estimate"] = gram24
    gold["gram21_sar_estimate"] = gram24 * 0.875
    gold["conversion_note"] = "تقديري قبل المصنعية؛ تحويل على أساس 3.75 ريال لكل دولار"

data["provider"] = "Yahoo Finance"
data["source_url"] = "https://finance.yahoo.com/"
data["updated_at"] = now
data["timezone"] = "Asia/Riyadh"
data["snapshot_note"] = "تحديث مجدول مرة واحدة بعد إغلاق السوق السعودي؛ القيم السابقة تبقى محفوظة إذا تعذر جلب سعر جديد."
OUT.parent.mkdir(parents=True, exist_ok=True)
tmp = OUT.with_suffix(".json.tmp")
tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
tmp.replace(OUT)
print("Snapshot saved:", OUT, "| updated quotes:", ", ".join(updated) or "none")
