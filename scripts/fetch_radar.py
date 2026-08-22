#!/usr/bin/env python3
"""fetch_radar.py — رادار رقبا: دریافت تقویم اتاق‌های هدف از API جاجیگا
=====================================================================
منبع: api.jajiga.com/api/nights?room_id={id}  (بدون auth)

طراحی:
    - اتاق‌ها از radar_common (data/radar/radar-config.json) — اضافه‌کردن
      رقیب با radar_add_room.py، بدون دست زدن به کد
    - فچ موازی با ThreadPool (پیش‌فرض ۴ همزمان) → مقیاس‌پذیری تا ده‌ها
      اتاق؛ retry نمایی + jitter برای rate-limit
    - داده خام کامل (همه شب‌ها) ذخیره می‌شود → داده لایه بدون از دست رفتن
      (فیلتر ماه جاری + ماه بعد شمسی در سمت داشبورد انجام می‌شود)
    - متادیتا از data/pricing/pricing-dataset.json + fallback
      data/supply-data.json (اتاق‌هایی که در pricing نیستند)
    - قانون طلایی تقویم: روزهای گذشته (date < today) هرگز پر حساب نمی‌شوند
    - نیمه‌پر (turnover) = شب قبل پر + امروز خالی → در داشبورد تشخیص داده می‌شود

خروجی:
    data/radar/{room_id}.json               — آخرین تقویم هر اتاق (کامل)
    data/radar/snapshots/{YYYY-MM-DD}.json  — اسنپ‌شات روزانه همه اتاق‌ها
"""
import json
import os
import random
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

from radar_common import ROOMS, ROOM_IDS, LABELS, OWN_IDS

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
RADAR_DIR = os.path.join(ROOT, "data", "radar")
SNAPSHOT_DIR = os.path.join(RADAR_DIR, "snapshots")
PRICING_FILE = os.path.join(ROOT, "data", "pricing", "pricing-dataset.json")
SUPPLY_FILE = os.path.join(ROOT, "data", "supply-data.json")
MANUAL_BLOCKS_FILE = os.path.join(ROOT, "data", "manual-blocks.json")

API = "https://api.jajiga.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
DELAY_MIN, DELAY_MAX = 0.4, 1.2     # jitter بین ریکوئست‌های موازی
MAX_ATTEMPTS = 4
CONCURRENCY = 4                      # ۴ اتاق همزمان — زیر حد rate-limit

# سازگاری با اسکریپت‌های قدیمی‌تر — منبع واقعی radar_common/کانفیگ است
RADAR_ROOM_IDS = ROOM_IDS

MANUAL_BLOCKS = {}  # room_id_str -> set of ISO dates (بارگذاری در main)

_print_lock = threading.Lock()


def load_meta():
    """متادیتای اتاق‌ها: pricing → fallback supply → برچسب کانفیگ.

    پرچم own از کانفیگ (radar-config.json) قطعی است.
    """
    meta = {}
    try:
        for r in json.load(open(PRICING_FILE, encoding="utf-8")):
            if r.get("id") in RADAR_ROOM_IDS:
                meta[r["id"]] = {
                    "title": r.get("title"),
                    "village": r.get("village"),
                    "host_name": r.get("host_name"),
                    "host_id": r.get("host_id"),
                    "min_price": r.get("min_price"),
                    "own": bool(r.get("own")),
                }
    except Exception:
        pass

    missing = [rid for rid in RADAR_ROOM_IDS if rid not in meta]
    if missing:
        try:
            supply = json.load(open(SUPPLY_FILE, encoding="utf-8"))
            rooms_list = supply.get("rooms") or (supply if isinstance(supply, list) else [])
            for r in rooms_list:
                if r.get("id") in missing:
                    meta[r["id"]] = {
                        "title": r.get("title"),
                        "village": r.get("village"),
                        "host_name": r.get("host_name"),
                        "host_id": r.get("host_id"),
                        "min_price": r.get("price"),
                        "own": False,
                    }
        except Exception:
            pass

    for rid in RADAR_ROOM_IDS:
        m = meta.setdefault(rid, {"title": None, "village": None,
                                  "host_name": None, "host_id": None,
                                  "min_price": None, "own": False})
        m["title"] = m.get("title") or LABELS.get(rid)
        m["own"] = bool(OWN_IDS and rid in OWN_IDS) or m.get("own")
    return meta


def fetch_nights(room_id):
    """تقویم کامل یک اتاق را می‌گیرد. Returns list of night dicts."""
    url = f"{API}/api/nights?room_id={room_id}"
    last_err = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=25) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            nights = raw.get("nights") or []
            if nights:
                return nights
            last_err = RuntimeError("empty nights payload")
        except Exception as e:
            last_err = e
        if attempt < MAX_ATTEMPTS - 1:
            time.sleep((2 ** attempt) * 5)
    raise last_err


def load_manual_blocks():
    """روزهای «بسته میزبان» (غیرمشتری) از data/manual-blocks.json.
    Returns dict: room_id_str -> set of ISO dates."""
    try:
        data = json.load(open(MANUAL_BLOCKS_FILE, encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for rid, dates in (data or {}).items():
        if isinstance(dates, list):
            out[str(rid)] = set(d for d in dates if isinstance(d, str))
    return out


def fetch_one(rid, meta):
    """فچ یک اتاق → فایل JSON. خروجی (rid, record|None, error|None)."""
    try:
        nights = fetch_nights(rid)
        blocked = MANUAL_BLOCKS.get(str(rid))
        if blocked:
            for n in nights:
                if n.get("date") in blocked:
                    n["is_manual_block"] = True
        record = {
            "room_id": rid,
            "meta": meta,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "nights": nights,
        }
        with open(os.path.join(RADAR_DIR, f"{rid}.json"), "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        with _print_lock:
            print(f"  [ok] {rid} | {len(nights)} nights | {(meta.get('title') or '')[:40]}", flush=True)
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))  # jitter بین موج‌ها
        return rid, record, None
    except Exception as e:
        with _print_lock:
            print(f"  [ERR] {rid} | {str(e)[:60]}", flush=True)
        return rid, None, str(e)[:80]


def main():
    os.makedirs(RADAR_DIR, exist_ok=True)
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    global MANUAL_BLOCKS
    MANUAL_BLOCKS = load_manual_blocks()
    meta = load_meta()
    today = date.today()
    print(f"Radar rooms: {len(RADAR_ROOM_IDS)} (concurrency {CONCURRENCY}) | fetched at {today}", flush=True)

    ok = 0
    failed = []
    snapshot = {"fetched_at": datetime.now(timezone.utc).isoformat(), "rooms": {}}

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futures = {ex.submit(fetch_one, rid, meta.get(rid, {})): rid for rid in RADAR_ROOM_IDS}
        for fut in as_completed(futures):
            rid, record, err = fut.result()
            if record:
                snapshot["rooms"][str(rid)] = {"meta": record["meta"], "nights": record["nights"]}
                ok += 1
            else:
                failed.append((rid, err))

    # --- ضد-اسنپ‌شات ناقص: اگر اتاقی فچ نشد، رکورد قبلی‌اش را نگه دار ---
    # (قبلاً overwrite کامل بود؛ چند شکست موازی → اسنپ‌شات ۳/۳۵ اتاقی و
    #  داشبورد آن روز تقریباً خالی. حالا فقط اتاق‌های تازه‌فچ شده «تازه»اند.)
    if failed:
        snap_file_prev = os.path.join(SNAPSHOT_DIR, today.isoformat() + ".json")
        prev = {}
        try:
            if os.path.exists(snap_file_prev):
                prev = (json.load(open(snap_file_prev, encoding="utf-8")).get("rooms")) or {}
        except Exception:
            prev = {}
        carried = 0
        for rid, _err in failed:
            key = str(rid)
            old = prev.get(key) or _prev_day_room(SNAPSHOT_DIR, today, key)
            if old:
                snapshot["rooms"][key] = {
                    "meta": old.get("meta") or {},
                    "nights": old.get("nights") or [],
                    "carried_from_previous_fetch": True,
                }
                carried += 1
        if carried:
            print(f"carried {carried} room(s) from earlier fetch of today / yesterday", flush=True)

    snap_file = os.path.join(SNAPSHOT_DIR, today.isoformat() + ".json")
    # overwrite: هر اجرا داده تازه می‌نویسد، ولی اتاق‌های ناموفق از فچ قبلی
    # همان روز (یا آخرین اسنپ‌شات موجود) حمل می‌شوند تا اسنپ‌شات ناقص نماند.
    with open(snap_file, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"Radar fetch: {ok}/{len(RADAR_ROOM_IDS)} fresh OK, "
          f"{len(snapshot['rooms'])} rooms in snapshot, {len(failed)} failed")
    for rid, err in failed:
        print(f"  ERR {rid}: {err}")
    print(f"Saved: data/radar/*.json + snapshots/{today}.json")


def _prev_day_room(snapshot_dir, today, rid_key):
    """آخرین رکورد موجود برای این اتاق از اسنپ‌شات‌های روزهای قبل."""
    import glob
    files = sorted(glob.glob(os.path.join(snapshot_dir, "*.json")), reverse=True)
    for fp in files[:5]:  # حداکثر ۵ روز عقب برو
        base = os.path.basename(fp)[:10]
        if base >= today.isoformat():
            continue
        try:
            rooms = json.load(open(fp, encoding="utf-8")).get("rooms") or {}
            if rid_key in rooms:
                return rooms[rid_key]
        except Exception:
            continue
    return None


if __name__ == "__main__":
    main()
