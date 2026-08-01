#!/usr/bin/env python3
"""
fetch_occupancy.py — محاسبه درصد اشغال ۳۰ روز آینده برای هر کلبه
=============================================================
از API تقویم جاجیگا (`/api/nights`) استفاده میکند — بدون auth، بدون مرورگر.

قانون طلایی (از RND-calendar.md):
    اول چک کن date < today → گذشته (حتی اگر is_unavailable=True)
    بعد is_unavailable → پر
    وگرنه → خالی

قانون غیرفعال (2026-08-01, user):
    اقامتگاه غیرفعال (active=false) همیشه اشغال 0 میگیرد —
    درصد اشغال فقط برای اقامتگاههای فعال معنا دارد (رزروهای
    قدیمی یک اقامتگاه بسته، سیگنال تقاضا نیست).

Usage:
    python scripts/fetch_occupancy.py               # همه کلبهها
    python scripts/fetch_occupancy.py --rooms 1,2   # فقط چند کلبه
"""
import json
import os
import random
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_FILE = os.path.join(PROJECT_ROOT, "data", "all-cabins.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
API = "https://api.jajiga.com"
DELAY_MIN, DELAY_MAX = 2.0, 4.0
MAX_RETRIES = 3
OCCUPANCY_WINDOW_DAYS = 30


def fetch_nights(room_id):
    """Fetch calendar for a room. Returns list of night dicts or raises."""
    url = f"{API}/api/nights?room_id={room_id}"
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=25) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            nights = raw.get("nights", [])
            if not nights:
                raise ValueError("empty nights payload")
            return nights
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep((2 ** attempt) * 5)
    raise last_err


def calc_occupancy(nights, window_days=OCCUPANCY_WINDOW_DAYS):
    """Percent of the next `window_days` days that are unavailable.

    GOLDEN RULE: days before today are PAST (never count as booked),
    even if they carry is_unavailable=true.
    """
    today = date.today()
    end = today + timedelta(days=window_days)

    total = 0
    unavailable = 0
    for n in nights:
        try:
            d = date.fromisoformat(n["date"])
        except (KeyError, ValueError):
            continue
        if d < today or d >= end:
            continue
        total += 1
        if n.get("is_unavailable"):
            unavailable += 1

    if total == 0:
        return 0, 0, total
    pct = round((unavailable / total) * 100)
    return pct, unavailable, total


def main():
    rooms_filter = None
    if "--rooms" in sys.argv:
        i = sys.argv.index("--rooms")
        rooms_filter = {int(x) for x in sys.argv[i + 1].split(",") if x.strip()}

    data = json.load(open(DATA_FILE, encoding="utf-8"))
    villages = data["villages"]

    all_cabins = []
    for vname, cabins in villages.items():
        for c in cabins:
            all_cabins.append((vname, c))

    if rooms_filter:
        all_cabins = [(v, c) for v, c in all_cabins if c["id"] in rooms_filter]

    print(f"Processing {len(all_cabins)} rooms...", flush=True)
    ok = 0
    failed = []
    for i, (vname, cabin) in enumerate(all_cabins, 1):
        rid = cabin["id"]

        # INACTIVE RULE: occupancy only matters for active listings.
        # An inactive cabin's calendar may still carry old bookings
        # (host closed but reservations remain) — that is NOT a demand
        # signal, so it always gets 0%.
        if not cabin.get("active", True):
            cabin["occupancy_30"] = 0
            cabin["occupancy_30_unavailable"] = 0
            cabin["occupancy_30_total"] = 30
            cabin["last_occupancy_attempt"] = datetime.now(timezone.utc).isoformat()
            ok += 1
            if rooms_filter or i % 5 == 0:
                print(f"  [{i}/{len(all_cabins)}] {rid} | INACTIVE → 0%", flush=True)
            if i < len(all_cabins):
                time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            continue

        try:
            nights = fetch_nights(rid)
            pct, unavailable, total = calc_occupancy(nights)
            cabin["occupancy_30"] = pct
            cabin["occupancy_30_unavailable"] = unavailable
            cabin["occupancy_30_total"] = total
            cabin["last_occupancy_attempt"] = datetime.now(timezone.utc).isoformat()
            ok += 1
            if i % 5 == 0 or rooms_filter:
                print(f"  [{i}/{len(all_cabins)}] {rid} | {pct}% ({unavailable}/{total})", flush=True)
        except Exception as e:
            failed.append((rid, str(e)[:80]))
            print(f"  [{i}/{len(all_cabins)}] {rid} ERROR: {str(e)[:60]}", flush=True)
        if i < len(all_cabins):
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    data["meta"]["occupancy_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"Occupancy fetch: {ok}/{len(all_cabins)} OK, {len(failed)} failed")
    for rid, err in failed:
        print(f"  ERR {rid}: {err}")
    print(f"Saved to {DATA_FILE}")

    # Summary by category
    from collections import Counter
    cats = Counter()
    for vname, c in all_cabins:
        p = c.get("occupancy_30", -1)
        if p < 0:
            cats["no data"] += 1
        elif p <= 5:
            cats["خالی 0-5%"] += 1
        elif p <= 15:
            cats["نیمه‌پر 5-15%"] += 1
        else:
            cats["پر 15%+"] += 1
    print(f"Categories: {dict(cats)}")


if __name__ == "__main__":
    main()
