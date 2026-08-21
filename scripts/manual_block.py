#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""manual_block.py — مدیریت روزهای «بسته میزبان» (non-customer blocks)
=====================================================================
روزهایی که میزبان خودش در جاجیگا می‌بندد ولی برای مشتری نیست. این روزها:
    - در داشبورد رادار با ظاهر متفاوت (راه‌خط) دیده می‌شوند
    - در تخمین درآمد حساب نمی‌شوند
    - در دیتابیس فلگ is_manual_block می‌گیرند

کاربرد:
    python manual_block.py add <room_id> <YYYY-MM-DD> [<YYYY-MM-DD> ...]
    python manual_block.py remove <room_id> <YYYY-MM-DD> [<YYYY-MM-DD> ...]
    python manual_block.py list

پس از add/remove، برای اعمال در داشبوردها و دیتابیس باید pipeline اجرا شود:
    python radar_daily.py   (یا fetch_radar + build_radar_dashboard + fetch_revenue + build_revenue_dashboard + db_build + db_export)
"""
import json
import os
import sys
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
BLOCKS_FILE = os.path.join(ROOT, "data", "manual-blocks.json")


def load():
    if os.path.exists(BLOCKS_FILE):
        try:
            data = json.load(open(BLOCKS_FILE, encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def save(data):
    with open(BLOCKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def valid_dates(args):
    """اعتبارسنجی تاریخ‌های ورودی. Returns list of 'YYYY-MM-DD'."""
    out = []
    for a in args:
        try:
            d = date.fromisoformat(a)
            out.append(d.isoformat())
        except ValueError:
            print(f"  ❌ تاریخ نامعتبر: {a} (قالب باید YYYY-MM-DD باشد)")
            sys.exit(1)
    return out


def cmd_add(room_id, dates):
    data = load()
    key = str(room_id)
    existing = set(data.get(key, []))
    added = [d for d in dates if d not in existing]
    existing.update(added)
    data[key] = sorted(existing)
    save(data)
    print(f"  ✅ {len(added)} روز به «بسته میزبان» اتاق {key} اضافه شد: {', '.join(added)}")
    print("  ⚠️ برای اعمال: python scripts/radar_daily.py (یا pipeline دستی)")


def cmd_remove(room_id, dates):
    data = load()
    key = str(room_id)
    existing = set(data.get(key, []))
    removed = [d for d in dates if d in existing]
    existing.difference_update(removed)
    if existing:
        data[key] = sorted(existing)
    else:
        data.pop(key, None)
    save(data)
    print(f"  ✅ {len(removed)} روز حذف شد: {', '.join(removed) if removed else '—'}")
    print("  ⚠️ برای اعمال: python scripts/radar_daily.py (یا pipeline دستی)")


def cmd_list():
    data = load()
    if not data:
        print("  (خالی)")
        return
    for rid, dates in sorted(data.items()):
        if rid == "_comment":
            continue  # توضیح فایل JSON — اتاق نیست
        print(f"  اتاق {rid}: {len(dates)} روز")
        for d in dates:
            print(f"    - {d}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "list":
        cmd_list()
    elif cmd == "add" and len(sys.argv) >= 4:
        cmd_add(sys.argv[2], valid_dates(sys.argv[3:]))
    elif cmd == "remove" and len(sys.argv) >= 4:
        cmd_remove(sys.argv[2], valid_dates(sys.argv[3:]))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
