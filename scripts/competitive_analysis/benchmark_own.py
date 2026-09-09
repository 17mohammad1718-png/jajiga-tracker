#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""benchmark_own.py — تسک ۲: بنچمارک کلبه 3297585 در برابر بازار
صدک هر متریک: (الف) در برابر 395 کلبه اصلی (ب) در برابر سیدکلا
خروجی: analysis/own_benchmark.csv + چاپ جدول
"""
import csv
import json
import os

ROOT = r"H:/projects/jajiga-tracker"
ANA = os.path.join(ROOT, "exports", "competitive_2026-09-08", "analysis")
OWN_ID = "3297585"

rows = json.load(open(os.path.join(ANA, "analysis_rooms.json"), encoding="utf-8"))
own = next(r for r in rows if r["شناسه"] == OWN_ID)
main = [r for r in rows if r["دسته"] == "main" and r["شناسه"] != OWN_ID]
seyed = [r for r in main if r["روستا"] == "سیدکلا"]

def pct_score(values, x):
    """صدک x در values (بالاتر = درصد کلیدهای کمتر یا مساوی) — فقط مقادیر غیرخالی"""
    vals = sorted(v for v in values if v is not None)
    if not vals or x is None:
        return None
    below = sum(1 for v in vals if v <= x)
    return round(below * 100.0 / len(vals), 0)

def median(values):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    n = len(vals)
    return round(vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2, 1)

METRICS = [
    ("قیمت_دوشب_آخر_هفته", "قیمت دو شب آخرهفته (تومان)"),
    ("قیمت_دوشب_وسط_هفته", "قیمت دو شب وسطهفته (تومان)"),
    ("امتیاز_کلی", "امتیاز کلی"),
    ("تعداد_نظرات", "تعداد نظرات"),
    ("success_books", "رزرو موفق انباشته"),
    ("کتاب_بر_ماه", "رزرو به‌ازای ماه عمر"),
    ("متراژ_بنا", "متراژ بنا"),
]

out = []
print(f"=== بنچمارک {own['عنوان']} (3297585) ===")
print(f"مقایسه با {len(main)} کلبه اصلی بازار / {len(seyed)} کلبه سیدکلا\n")
hdr = f"{'متریک':32s} {'من':>12s} {'صدک بازار':>10s} {'میانه بازار':>12s} {'صدک سیدکلا':>11s} {'میانه سیدکلا':>13s}"
print(hdr)
for key, label in METRICS:
    mine = own.get(key)
    p_market = pct_score([r.get(key) for r in main], mine)
    med_market = median([r.get(key) for r in main])
    p_seyed = pct_score([r.get(key) for r in seyed], mine)
    med_seyed = median([r.get(key) for r in seyed])
    n_market = sum(1 for r in main if r.get(key) is not None)
    n_seyed = sum(1 for r in seyed if r.get(key) is not None)
    out.append({
        "متریک": label, "کلید": key, "من": mine,
        "صدک_بازار": p_market, "میانه_بازار": med_market, "n_بازار": n_market,
        "صدک_سیدکلا": p_seyed, "میانه_سیدکلا": med_seyed, "n_سیدکلا": n_seyed,
    })
    print(f"{label:32s} {str(mine):>12s} {(str(p_market) + '%') if p_market is not None else '-':>10s} {str(med_market):>12s} "
          f"{str(p_seyed) + '%' if p_seyed is not None else '-':>11s} {str(med_seyed):>13s}")

with open(os.path.join(ANA, "own_benchmark.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)

# زمینه: چند کلبه سیدکلا قیمت‌دارند و توزیعشان
prices_seyed = sorted(r["قیمت_دوشب_آخر_هفته"] for r in seyed if r.get("قیمت_دوشب_آخر_هفته"))
print(f"\nسیدکلا: {len(prices_seyed)} کلبه قیمت‌دار از {len(seyed)} — دامنه {prices_seyed[0]:,} تا {prices_seyed[-1]:,}")
print("توزیع قیمت دو شب آخرهفته سیدکلا:", prices_seyed)
