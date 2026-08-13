#!/usr/bin/env python3
"""
supply_snapshot.py — اسنپشات روزانه عرضه بابلکنار
==================================================
هر روز کل لیست اتاق‌های بابلکنار را اسکن می‌کند و:
    - data/snapshots/supply-YYYY-MM-DD.json را ذخیره می‌کند
      {date, meta_counts: {babolkenar, cottage}, room_ids: [...]}
    - با اسنپشات قبلی مقایسه می‌کند → چاپ "+N added, -M removed"

طراحی برای cron (no_agent=True):
    - وقتی تغییری نباشد خروجی خالی → کرون ساکت می‌ماند
    - وقتی تغییری باشد فقط همان خط diff چاپ می‌شود

نکته: pagination درون url پارامتر (از iran-ecommerce-scraping skill):
    url=https://www.jajiga.com/s/babolkenar?page=N — نه page= بالای API

Usage:
    python scripts/supply_snapshot.py          # اجرای کامل
    python scripts/supply_snapshot.py --quiet  # بدون چاپ جزئیات
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SNAP_DIR = os.path.join(PROJECT_ROOT, "data", "snapshots")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
API = "https://api.jajiga.com"
PER_PAGE = 18
QUIET = "--quiet" in sys.argv


def fetch_json(url, retries=5):
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < retries:
                time.sleep((2 ** attempt) * 5)
    raise last_err


def market_count(page_path):
    """meta.rooms_count for a page URL (one no-auth call)."""
    url = f"{API}/api/search?per_page=1&url={urllib.parse.quote(page_path, safe='')}"
    d = fetch_json(url)
    return (d.get("meta") or {}).get("rooms_count")


def sweep_room_ids():
    """In-url pagination sweep of /s/babolkenar → all room ids."""
    ids = set()
    page = 1
    while True:
        page_url = f"https://www.jajiga.com/s/babolkenar?page={page}"
        api_url = f"{API}/api/search?per_page={PER_PAGE}&page={page}&url={urllib.parse.quote(page_url, safe='')}&with[]=rooms"
        d = fetch_json(api_url)
        items = ((d.get("rooms") or {}).get("items")) or []
        if not items:
            break
        for it in items:
            ids.add(int(it["id"]))
        if not QUIET:
            print(f"  page {page}: +{len(items)} (total {len(ids)})", flush=True)
        page += 1
        time.sleep(0.8)
    return ids


def main():
    today = date.today().isoformat()
    os.makedirs(SNAP_DIR, exist_ok=True)

    if not QUIET:
        print(f"Snapshot {today}: sweeping babolkenar...", flush=True)
    ids = sweep_room_ids()
    if not ids:
        print("ERROR: empty sweep — network/API problem", file=sys.stderr)
        sys.exit(1)

    counts = {}
    try:
        counts["babolkenar"] = market_count("https://www.jajiga.com/s/babolkenar")
        counts["cottage"] = market_count("https://www.jajiga.com/s/babolkenar/cottage")
    except Exception as e:  # noqa: BLE001
        if not QUIET:
            print(f"market-count warn: {e}")

    snap = {"date": today, "meta_counts": counts, "room_ids": sorted(ids)}
    path = os.path.join(SNAP_DIR, f"supply-{today}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)

    # diff vs previous
    prev_path = None
    prev = None
    if os.path.exists(SNAP_DIR):
        snaps = sorted(f for f in os.listdir(SNAP_DIR) if f.startswith("supply-") and f.endswith(".json") and f < f"supply-{today}.json")
        if snaps:
            prev_path = os.path.join(SNAP_DIR, snaps[-1])
            with open(prev_path, encoding="utf-8") as f:
                prev = json.load(f)

    if prev:
        prev_ids = set(prev["room_ids"])
        added = sorted(ids - prev_ids)
        removed = sorted(prev_ids - ids)
        if added or removed:
            print(f"+{len(added)} added, -{len(removed)} removed (vs {prev['date']})")
            for rid in added[:20]:
                print(f"  + https://www.jajiga.com/room/{rid}")
            for rid in removed[:20]:
                print(f"  - https://www.jajiga.com/room/{rid}")
        else:
            if not QUIET:
                print(f"no change vs {prev['date']}")
    else:
        print(f"first snapshot: {len(ids)} rooms (baseline)")

    if not QUIET:
        print(f"saved {path} | total={len(ids)} counts={counts}")


if __name__ == "__main__":
    main()
