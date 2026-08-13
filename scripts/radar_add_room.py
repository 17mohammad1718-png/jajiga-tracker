#!/usr/bin/env python3
"""radar_add_room.py — افزودن سریع رقیب به رادار (بدون دست زدن به کد)
====================================================================
اتاق را به data/radar/radar-config.json اضافه می‌کند؛ متادیتا (عنوان،
روستا، میزبان) را خودکار از API جاجیگا + دیتاست‌های محلی می‌گیرد.

استفاده:
    python scripts/radar_add_room.py 1234567                     # خودکار + پیشنهاد برچسب
    python scripts/radar_add_room.py 1234567 "برچسب کوتاه"       # برچسب دلخواه برای تلگرام
    python scripts/radar_add_room.py 1234567 "برچسب" --fetch     # بلافاصله تقویم هم بگیر
    python scripts/radar_add_room.py 1234567 --dry-run           # فقط پیش‌نمایش، ذخیره نکند

خروجی موفق:
    ✅ افزوده شد: 3240445 | کلبه سوئیسی ... | سیدکلا | امیر | short=امیر
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from radar_common import CONFIG_FILE, ROOMS, ROOM_IDS, LABELS, load_config, save_config  # noqa: E402

API = "https://api.jajiga.com"
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/125.0.0.0 Safari/537.36")}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
PRICING_FILE = os.path.join(ROOT, "data", "pricing", "pricing-dataset.json")
SUPPLY_FILE = os.path.join(ROOT, "data", "supply-data.json")

VILLAGE_ALIASES = ["سیدکلا", "سید کلا", "گونه کلا", "گونهکلا", "شیردارکلا",
                   "قرآن تالار", "قران تالار", "کاردرکلا", "امیرکلا"]


def fetch_room_meta(rid):
    """متادیتای اتاق را از API می‌گیرد: عنوان + میزبان."""
    req = urllib.request.Request(f"{API}/api/room/{rid}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as resp:
        d = json.loads(resp.read().decode("utf-8"))
    host = d.get("host") or {}
    return {
        "title": d.get("title"),
        "host_name": d.get("host_name") or host.get("name"),
        "host_id": d.get("host_id") or host.get("id"),
    }


def detect_village(rid, title):
    """روستا: اول دیتاست‌های محلی، بعد از پسوند عنوان بعد از 'بابلکنار'."""
    for f in (PRICING_FILE, SUPPLY_FILE):
        try:
            data = json.load(open(f, encoding="utf-8"))
            rooms = data.get("rooms") if isinstance(data, dict) else data
            for r in rooms or []:
                if r.get("id") == rid and r.get("village"):
                    return r["village"]
        except Exception:
            continue
    if title:
        for v in VILLAGE_ALIASES:
            if v in title:
                return "سیدکلا" if v == "سید کلا" else v
        m = re.search(r"بابلکنار\s*-\s*([^-]+)$", title)
        if m:
            return m.group(1).strip()
    return "—"


def main():
    ap = argparse.ArgumentParser(description="افزودن رقیب به رادار جاجیگا")
    ap.add_argument("room_id", type=int, help="شناسه اتاق (آخرین عدد آدرس /room/...)")
    ap.add_argument("short_label", nargs="?", default=None, help="برچسب کوتاه برای تلگرام (اختیاری)")
    ap.add_argument("--fetch", action="store_true", help="بعد از افزودن، فچ تقویم هم بزن")
    ap.add_argument("--dry-run", action="store_true", help="فقط پیش‌نمایش؛ چیزی ذخیره نکند")
    args = ap.parse_args()

    rid = args.room_id
    if rid in ROOM_IDS:
        print(f"⚠️  اتاق {rid} از قبل در رادار هست (label: {LABELS.get(rid, '')})")
        return

    print(f"Fetching meta for room {rid} ...", flush=True)
    try:
        meta = fetch_room_meta(rid)
    except Exception as e:
        print(f"❌ دریافت متادیتا از API ناموفق: {e}")
        sys.exit(1)

    title = meta.get("title") or f"اتاق {rid}"
    village = detect_village(rid, title)
    host = meta.get("host_name") or str(rid)
    short = args.short_label or host.split()[0]

    print("\n" + "=" * 56)
    print(f"  ID      : {rid}")
    print(f"  عنوان   : {title}")
    print(f"  روستا   : {village}")
    print(f"  میزبان  : {host}")
    print(f"  برچسب   : {short}")
    print("=" * 56)

    if args.dry_run:
        print("(dry-run — چیزی ذخیره نشد)")
        return

    cfg = load_config()
    cfg.setdefault("rooms", []).append({
        "id": rid,
        "label": title,
        "short_label": short,
        "own": False,
    })
    save_config(cfg)
    print(f"✅ افزوده شد: {rid} | {title} | {village} | {host} | short={short}")

    if args.fetch:
        print("Fetching calendar ...")
        subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "fetch_radar.py")])


if __name__ == "__main__":
    main()
