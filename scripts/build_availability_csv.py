#!/usr/bin/env python3
"""build_availability_csv.py — خروجی سوم: availability_30d.csv
پرچم روزبه‌روز ۳۰ روز آینده (برش امروز + ۳۰ شب) برای همه اقامتگاه‌های اصلی.
هیچ تفسیری: فقط is_unavailable مشاهده‌شده. روز بسته معادل رزرو نیست.
long format: هر (اقامتگاه، روز) یک ردیف.
"""
import csv, glob, json, os
from datetime import date

ROOT = r"H:/projects/jajiga-tracker"
N_DIR = os.path.join(ROOT, "data", "competitive", "nights")
OUT_DIR = os.path.join(ROOT, "exports", "competitive_2026-09-08")
TODAY = date(2026, 9, 8)
END = TODAY + __import__("datetime").timedelta(days=30)

COLS = ["شناسه", "روستا", "تاریخ_میلادی", "وضعیت_مشاهده_شده", "قیمت_شب_تومان",
        "تخفیف_درصد", "پرچم_تعطیل_از_API", "پرچم_آخر_هفته_از_API", "تاریخ_مشاهده"]

roster = json.load(open(os.path.join(ROOT, "data", "competitive", "roster.json"), encoding="utf-8"))
main_ids = {e["id"]: e for e in roster["main"]}

rows = []
for p in sorted(glob.glob(os.path.join(N_DIR, "*.json")), key=lambda x: int(os.path.basename(x)[:-5])):
    rid = int(os.path.basename(p)[:-5])
    if rid not in main_ids: continue
    e = main_ids[rid]
    d = json.load(open(p, encoding="utf-8"))
    for nt in d.get("nights") or []:
        dt = nt.get("date") or ""
        if not dt or dt < str(TODAY) or dt > str(END): continue
        if nt.get("is_unavailable"):
            status = "بسته (مشاهده‌شده - دلیل نامشخص)"
        elif nt.get("price") is not None:
            status = "باز"
        else:
            status = "بدون قیمت"
        rows.append({
            "شناسه": rid, "روستا": e.get("village",""), "تاریخ_میلادی": dt,
            "وضعیت_مشاهده_شده": status,
            "قیمت_شب_تومان": nt.get("price") if nt.get("price") is not None else "",
            "تخفیف_درصد": nt.get("discount") if nt.get("discount") is not None else "",
            "پرچم_تعطیل_از_API": "بله" if nt.get("is_holiday") else "",
            "پرچم_آخر_هفته_از_API": "بله" if nt.get("is_weekend") else "",
            "تاریخ_مشاهده": d.get("fetched_at",""),
        })

rows.sort(key=lambda r: (r["شناسه"], r["تاریخ_میلادی"]))
out = os.path.join(OUT_DIR, "availability_30d.csv")
with open(out, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
    w.writeheader(); w.writerows(rows)
closed = sum(1 for r in rows if r["وضعیت_مشاهده_شده"].startswith("بسته"))
print(f"availability_30d.csv: {len(rows)} rows, closed-observed={closed} -> {out}")
