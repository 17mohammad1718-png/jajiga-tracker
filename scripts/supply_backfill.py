#!/usr/bin/env python3
"""
supply_backfill.py — برآورد تاریخ ساخت اقامتگاه‌ها از روی عکس‌ها/نظرات
=====================================================================
جاجیگا تاریخ ساخت اقامتگاه را مستقیم نمی‌دهد. نزدیک‌ترین سیگنال‌ها:
    - اولین تاریخ آپلود عکس (pictures[].created_at از /api/room/{id})
      → عکس‌ها هنگام ساخت/ثبت اقامتگاه آپلود می‌شوند
    - اگر عکسی نبود: اولین تاریخ نظر (آخرین صفحه /reviews)
    - میزبان نمی‌تواند قبل از عضویت خودش اقامتگاه بسازد → تاریخ عضویت
      میزبان به عنوان حد پایین (clamp)

خروجی: data/supply/room-dates.json
    { "<room_id>": {id, title, status, host_id, host_created_at,
                    first_photo, photo_count, first_review, est_date}, ... }

نکته‌ها (از تجربه جاجیگا — iran-ecommerce-scraping skill):
    - فقط یک استریم — هرگز دو فرایند موازی (WinError 10061)
    - تأخیر تصادفی ۲-۳ ثانیه + retry با backoff
    - قابلیت ادامه: آیدی‌های موجود در خروجی رد می‌شوند

Usage:
    python scripts/supply_backfill.py            # همه
    python scripts/supply_backfill.py --limit 5  # تست
    python scripts/supply_backfill.py --rooms 1,2,3  # فقط چند اتاق
"""
import json
import math
import os
import random
import sys
import time
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUT_FILE = os.path.join(PROJECT_ROOT, "data", "supply", "room-dates.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
API = "https://api.jajiga.com"
DELAY_MIN, DELAY_MAX = 2.0, 3.0
MAX_RETRIES = 3


def fetch_json(url):
    """GET JSON with retry + exponential backoff. Raises on final failure."""
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 — network layer, retry all
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep((2 ** attempt) * 5)
    raise last_err


def collect_room_ids():
    """Union of room ids from hosts DB + tracked cabins."""
    ids = {}
    hosts_path = os.path.join(PROJECT_ROOT, "data", "hosts-babolkenar.json")
    with open(hosts_path, encoding="utf-8") as f:
        hosts_db = json.load(f)
    for h in hosts_db.get("hosts", []):
        for r in h.get("rooms", []):
            ids[int(r["id"])] = r.get("title") or ""

    cabins_path = os.path.join(PROJECT_ROOT, "data", "all-cabins.json")
    with open(cabins_path, encoding="utf-8") as f:
        cabins_db = json.load(f)
    for v, cabs in cabins_db.get("villages", {}).items():
        for c in cabs:
            ids[int(c["id"])] = c.get("title") or ""
    return ids


def fetch_first_review(room_id):
    """Earliest review date via last page of /reviews (sorted newest first)."""
    first = fetch_json(f"{API}/api/room/{room_id}/reviews?per_page=10&page=1")
    total = (first.get("pagination") or {}).get("total", 0)
    if not total:
        return None
    page_count = math.ceil(total / 10)
    if page_count > 1:
        last = fetch_json(f"{API}/api/room/{room_id}/reviews?per_page=10&page={page_count}")
        items = last.get("items", [])
    else:
        items = first.get("items", [])
    dates = [it.get("created_at", "")[:10] for it in items if it.get("created_at")]
    return min(dates) if dates else None


def choose_est_date(first_photo, first_review, host_created_at):
    """min(photo, review), clamped to host join date as lower bound.

    عکس‌ها ممکن است دوباره آپلود شوند (اولین عکس دیرتر از ساخت واقعی).
    تاریخ عضویت میزبان = حد پایین: اقامتگاه نمی‌تواند قبل از عضویت ساخته
    شده باشد.
    """
    candidates = [d for d in (first_photo, first_review) if d]
    est = min(candidates) if candidates else None
    if est and host_created_at and est < host_created_at:
        est = host_created_at
    return est


def process_room(room_id):
    """Fetch room + estimate date. Returns record dict."""
    room = fetch_json(f"{API}/api/room/{room_id}")
    pics = room.get("pictures") or []
    photo_dates = [p.get("created_at") for p in pics if p.get("created_at")]
    first_photo = min(photo_dates) if photo_dates else None

    host = room.get("host") or {}
    host_created = (host.get("created_at") or "")[:10] or None

    first_review = None
    if not photo_dates:
        # بدون عکس → تلاش با اولین نظر (یک فراخوانی اضافه)
        try:
            first_review = fetch_first_review(room_id)
        except Exception:  # noqa: BLE001 — review fallback is best-effort
            first_review = None

    est = choose_est_date(first_photo, first_review, host_created)
    return {
        "id": room_id,
        "title": room.get("title") or "",
        "status": room.get("status") or "unknown",
        "host_id": host.get("id"),
        "host_name": host.get("name"),
        "host_created_at": host_created,
        "first_photo": first_photo,
        "photo_count": len(photo_dates),
        "first_review": first_review,
        "est_date": est,
    }


def main():
    rooms_filter = None
    limit = None
    if "--rooms" in sys.argv:
        i = sys.argv.index("--rooms")
        rooms_filter = {int(x) for x in sys.argv[i + 1].split(",") if x.strip()}
    if "--limit" in sys.argv:
        i = sys.argv.index("--limit")
        limit = int(sys.argv[i + 1])

    # load existing (resume support)
    existing = {}
    if os.path.exists(OUT_FILE):
        with open(OUT_FILE, encoding="utf-8") as f:
            existing = json.load(f)

    all_ids = collect_room_ids()
    if rooms_filter:
        all_ids = {k: v for k, v in all_ids.items() if k in rooms_filter}
    if limit:
        pending = [k for k in all_ids if str(k) not in existing]
        all_ids = {k: all_ids[k] for k in pending[:limit]}

    todo = [rid for rid in all_ids if str(rid) not in existing]
    print(f"Total unique rooms: {len(all_ids)} | pending: {len(todo)}", flush=True)

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)

    def save():
        with open(OUT_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=1)

    ok = 0
    failed = []
    for i, rid in enumerate(todo, 1):
        key = str(rid)
        try:
            rec = process_room(rid)
            existing[key] = rec
            ok += 1
            if i % 25 == 0:
                print(f"  [{i}/{len(todo)}] ok={ok} fail={len(failed)}", flush=True)
                save()  # incremental checkpoint — resume-safe on crash
        except Exception as e:  # noqa: BLE001
            failed.append((rid, str(e)))
            print(f"  FAIL {rid}: {e}", flush=True)
        if i < len(todo):
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    save()

    dated = sum(1 for r in existing.values() if r.get("est_date"))
    print(f"Done. total={len(existing)} dated={dated} ok={ok} failed={len(failed)}")
    if failed:
        print("Failed ids:", [r[0] for r in failed])


if __name__ == "__main__":
    main()
