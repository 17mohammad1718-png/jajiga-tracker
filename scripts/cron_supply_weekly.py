#!/usr/bin/env python3
"""
cron_supply_weekly.py — بروزرسانی هفتگی داشبورد عرضه بابلکنار
==============================================================
مراحل:
    1. اسنپ‌شات روزانه (جمع‌آوری آیدی‌های فعلی + شمارش بازار)
    2. بکفیل افزایشی — فقط اتاق‌هایی که هنوز تاریخ ندارند
    3. بازسازی supply-data.json + تزریق در supply-dashboard.html

خروجی: خلاصه فارسی برای کرون (stdout).

Usage:
    python scripts/cron_supply_weekly.py
"""
import json
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(PROJECT_ROOT, "scripts")
PY = sys.executable


def run(name, *args):
    r = subprocess.run(
        [PY, os.path.join(SCRIPTS, name), *args],
        capture_output=True, text=True, encoding="utf-8",
    )
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    return r.returncode, out, err


def collect_known_ids():
    """آیدی‌هایی که هم‌اکنون در داده‌ها هستند (اتاق‌های DB میزبان‌ها + کلبه‌های پیگیری‌شده)."""
    ids = set()
    hdb = json.load(open(os.path.join(PROJECT_ROOT, "data", "hosts-babolkenar.json"), encoding="utf-8"))
    for h in hdb.get("hosts", []):
        for r in h.get("rooms", []):
            ids.add(str(r["id"]))
    cab = json.load(open(os.path.join(PROJECT_ROOT, "data", "all-cabins.json"), encoding="utf-8"))
    for v, cabs in cab.get("villages", {}).items():
        for c in cabs:
            ids.add(str(c["id"]))
    return ids


def main():
    lines = []

    # 1. snapshot
    rc, out, err = run("supply_snapshot.py", "--quiet")
    if out:
        lines.append(out)
    if rc != 0:
        lines.append(f"⚠️ خطا در اسنپ‌شات: {err[:200]}")

    # 2. incremental backfill
    dates_path = os.path.join(PROJECT_ROOT, "data", "supply", "room-dates.json")
    known = set()
    if os.path.exists(dates_path):
        known = set(json.load(open(dates_path, encoding="utf-8")).keys())
    all_ids = collect_known_ids()
    new_ids = sorted(all_ids - known)
    if new_ids:
        lines.append(f"بکفیل: {len(new_ids)} اتاق جدید (تخمین تاریخ ساخت)")
        rc, out, err = run("supply_backfill.py", "--rooms", ",".join(new_ids))
        lines.append(out or err)
    else:
        lines.append("بکفیل: اتاق جدیدی نبود")

    # 3. rebuild
    rc, out, err = run("supply_build.py")
    if rc == 0:
        lines.append("داشبورد عرضه بازسازی شد ✅")
    else:
        lines.append(f"⚠️ خطا در بازسازی: {err[:200]}")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
