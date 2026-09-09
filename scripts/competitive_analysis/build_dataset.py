#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_dataset.py — تسک ۱: دیتاست تحلیلی واحد از پیکره رقابتی 2026-09-08
ادغام: listings (main+other+around) + prices (pivot دو بازه) + availability_30d + جزئیات خام API
خروجی: exports/competitive_2026-09-08/analysis/analysis_rooms.csv (+ .json)
"""
import csv
import json
import os
import sqlite3
import unicodedata
from datetime import date

ROOT = r"H:/projects/jajiga-tracker"
OUT = os.path.join(ROOT, "exports", "competitive_2026-09-08")
ANA = os.path.join(OUT, "analysis")
os.makedirs(ANA, exist_ok=True)
DETAILS = os.path.join(ROOT, "data", "competitive", "details")

def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def to_int(v):
    v = (v or "").strip()
    if not v:
        return None
    # انگلیسی‌سازی ارقام فارسی
    v = "".join(chr(ord(c) - 1728) if "۰" <= c <= "۹" else c for c in v)
    v = v.replace(",", "")
    try:
        return int(float(v))
    except ValueError:
        return None

def to_float(v):
    v = (v or "").strip()
    if not v:
        return None
    v = "".join(chr(ord(c) - 1728) if "۰" <= c <= "۹" else c for c in v)
    try:
        return float(v)
    except ValueError:
        return None

def months_since(ds, today=None):
    """عمر به ماه از تاریخ ISO؛ None اگر تاریخ نامعتبر"""
    if not ds or not ds[:4].isdigit():
        return None
    today = today or date(2026, 9, 9)
    try:
        y, m, d = int(ds[:4]), int(ds[5:7] or 1), int(ds[8:10] or 1)
        start = date(y, m, d)
    except ValueError:
        return None
    return round((today - start).days / 30.44, 1)

# ---------- 1) listings ----------
listings = []
for fn, cat in [("listings.csv", "main"),
                ("listings_other_villa_rustic.csv", "other_villa_rustic"),
                ("listings_around.csv", "around")]:
    for r in read_rows(os.path.join(OUT, fn)):
        r["دسته"] = cat
        listings.append(r)

# ---------- 2) prices pivot ----------
prices = {}
for r in read_rows(os.path.join(OUT, "prices.csv")):
    rid = r["شناسه"]
    p = prices.setdefault(rid, {})
    key = "وسط_هفته" if r["بازه"] == "وسط_هفته" else "آخر_هفته"
    p[f"قیمت_دوشب_{key}"] = to_int(r.get("قیمت_نهایی_دو_شب"))
    p[f"وضعیت_قیمت_{key}"] = r.get("وضعیت_قیمت", "")
    p[f"تخفیف_{key}"] = to_int(r.get("تخفیف_کل"))
    if r.get("هزینه_نفر_اضافه_تومان"):
        p["هزینه_نفر_اضافه"] = to_int(r.get("هزینه_نفر_اضافه_تومان"))

# ---------- 3) availability 30d ----------
avail = {}
for r in read_rows(os.path.join(OUT, "availability_30d.csv")):
    rid = r["شناسه"]
    a = avail.setdefault(rid, {"closed": 0, "total": 0})
    a["total"] += 1
    if "بسته" in (r.get("وضعیت_مشاهده_شده") or ""):
        a["closed"] += 1

# ---------- 4) عمر آگهی: اولویت est_date دیتابیس، بعد اولین نظر، بعد عضویت میزبان ----------
est = {}
db = os.path.join(ROOT, "jajiga.db")
if os.path.exists(db):
    con = sqlite3.connect(db)
    for rid, ed in con.execute("SELECT id, est_date FROM rooms WHERE est_date IS NOT NULL"):
        est[str(rid)] = ed
    con.close()

# ---------- 5) جزئیات خام ----------
def load_detail(rid):
    p = os.path.join(DETAILS, f"{rid}.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            o = json.load(f)
        return o if isinstance(o, dict) and "_http_error" not in o else None
    except Exception:
        return None

# ---------- ساخت جدول ----------
rows = []
for r in listings:
    rid = r["شناسه"]
    d = load_detail(rid) or {}
    p = prices.get(rid, {})
    a = avail.get(rid, {"closed": None, "total": None})

    # عمر
    anchor, anchor_src = None, None
    if rid in est:
        anchor, anchor_src = est[rid], "db_est"
    elif r.get("تاریخ_اولین_نظر"):
        anchor, anchor_src = r["تاریخ_اولین_نظر"], "first_review"
    elif r.get("میزبان_عضویت_از"):
        anchor, anchor_src = r["میزبان_عضویت_از"], "host_member"
    age_m = months_since(anchor) if anchor else None

    sb = d.get("success_books")
    sb = int(sb) if isinstance(sb, (int, float)) else None
    bpm = round(sb / age_m, 2) if (sb is not None and age_m and age_m > 0) else None

    closed_rate = round(a["closed"] / a["total"], 3) if (a["total"] and a["total"] > 0) else None

    row = {
        "شناسه": rid,
        "عنوان": r.get("عنوان", ""),
        "دسته": r["دسته"],
        "روستا": r.get("روستا", ""),
        "روستا_مطمئن": 1 if r.get("روستا_مطمئن") == "بله" else 0,
        "متراژ_بنا": to_int(r.get("متراژ_بنا_م2")),
        "اتاق_خواب": to_int(r.get("تعداد_اتاق_خواب")),
        "ظرفیت_پایه": to_int(r.get("ظرفیت_پایه")),
        "ظرفیت_حداکثر": to_int(r.get("ظرفیت_حداکثر")),
        "امتیاز_کلی": to_float(r.get("امتیاز_کلی")),
        "تعداد_نظرات": to_int(r.get("تعداد_نظرات_API")),
        "جکوزی": 1 if r.get("جکوزی") == "دارد" else 0,
        "استخر": 1 if r.get("استخر") == "دارد" else 0,
        "حیاط_محصور": 1 if r.get("حیاط_اختصاصی_محصور") == "ذکر شده" else 0,
        "ویو_جنگل": 1 if r.get("چشم_انداز_جنگل") == "ذکر شده" else 0,
        "ویو_رودخانه": 1 if r.get("چشم_انداز_رودخانه") == "ذکر شده" else 0,
        "دربست": 1 if r.get("ملک_دربست_یا_مشترک") == "دربست" else 0,
        "حداقل_شب": to_int(r.get("حداقل_شب")),
        "هزینه_نفر_اضافه": p.get("هزینه_نفر_اضافه"),
        "قیمت_دوشب_وسط_هفته": p.get("قیمت_دوشب_وسط_هفته"),
        "وضعیت_قیمت_وسط_هفته": p.get("وضعیت_قیمت_وسط_هفته", ""),
        "قیمت_دوشب_آخر_هفته": p.get("قیمت_دوشب_آخر_هفته"),
        "وضعیت_قیمت_آخر_هفته": p.get("وضعیت_قیمت_آخر_هفته", ""),
        "روز_بسته_30d": a["closed"] if a["closed"] is not None else None,
        "نرخ_روز_بسته_30d": closed_rate,
        "success_books": sb,
        "عمر_ماه": age_m,
        "عمر_مبنا": anchor_src or "",
        "کتاب_بر_ماه": bpm,
        "پلاس": 1 if d.get("is_plus") else 0,
        "جدید": 1 if d.get("is_new") else 0,
        "رزرو_فوری": 1 if d.get("is_instant") else 0,
        "وضعیت_API": r.get("وضعیت_API", "") or d.get("status", ""),
    }
    rows.append(row)

# ---------- خروجی ----------
header = list(rows[0].keys())
with open(os.path.join(ANA, "analysis_rooms.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=header)
    w.writeheader()
    w.writerows(rows)
with open(os.path.join(ANA, "analysis_rooms.json"), "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)

# ---------- راستی‌آزمایی ----------
print("rows:", len(rows))
by_cat = {}
for r in rows:
    by_cat[r["دسته"]] = by_cat.get(r["دسته"], 0) + 1
print("by category:", by_cat)
own = next((r for r in rows if r["شناسه"] == "3297585"), None)
print("own:", {k: own[k] for k in ["قیمت_دوشب_آخر_هفته", "success_books", "عمر_ماه",
                                   "عمر_مبنا", "کتاب_بر_ماه", "امتیاز_کلی", "تعداد_نظرات"]} if own else "MISSING")
sb_n = sum(1 for r in rows if r["success_books"] is not None)
pr_n = sum(1 for r in rows if r["قیمت_دوشب_آخر_هفته"])
print("with success_books:", sb_n, "| with weekend price:", pr_n)
anchors = {}
for r in rows:
    anchors[r["عمر_مبنا"]] = anchors.get(r["عمر_مبنا"], 0) + 1
print("age anchors:", anchors)
