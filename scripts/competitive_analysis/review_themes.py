#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""review_themes.py — تسک ۴: مضامین ستایش/گلایه از 1450 نظر 29 اتاق برتر
روش: شمارش کلیدواژه‌ای (ریشه‌های فارسی) در متن نظر؛ تفکیک 5ستاره vs زیر5؛ گلایه‌ها از نظرات <=3
خروجی: analysis/review_themes.md
"""
import csv
import json
import os
from collections import Counter

ROOT = r"H:/projects/jajiga-tracker"
OUT = os.path.join(ROOT, "exports", "competitive_2026-09-08")
ANA = os.path.join(OUT, "analysis")

# ---------- بارگذاری ----------
reviews = []
with open(os.path.join(OUT, "reviews.csv"), encoding="utf-8-sig", newline="") as f:
    reviews = list(csv.DictReader(f))
print("reviews:", len(reviews))

def rating(r):
    v = (r.get("امتیاز") or "").strip()
    try:
        return float(v)
    except ValueError:
        return None

for r in reviews:
    r["_rating"] = rating(r)

star5 = [r for r in reviews if r["_rating"] == 5]
sub5 = [r for r in reviews if r["_rating"] is not None and r["_rating"] < 5]
low3 = [r for r in reviews if r["_rating"] is not None and r["_rating"] <= 3]
print(f"5star: {len(star5)} | <5: {len(sub5)} | <=3: {len(low3)}")

# ---------- کلیدواژه‌ها (ریشه‌های رایج؛ نرمال‌سازی نیم‌فاصله و ی/ک عربی) ----------
def norm(s):
    s = (s or "").replace("\u200c", " ").replace("ي", "ی").replace("ك", "ک")
    return s.lower()

THEMES = {
    "جکوزی": ["جکوزی", "جکوسی", "جكوزی"],
    "استخر": ["استخر"],
    "تمیزی و نظافت": ["تمیز", "پاکیز", "نظافت", "پاک بود", "خوشبو"],
    "میزبان و برخورد": ["میزبان", "برخورد", "مهربان", "خوش قول", "خوشقول", "مهمان نواز", "مهمان‌نواز", "مهمان نواز"],
    "مسیر دسترسی": ["مسیر", "جاده", "دسترسی", "خاکی", "آسفالت"],
    "سرویس بهداشتی/حمام": ["سرویس", "بهداشتی", "حمام", "دستشویی", "توالت"],
    "آرامش و دنج بودن": ["آرامش", "دنج", "سکوت", "آرام"],
    "طبیعت و چشم‌انداز": ["منظره", "ویو", "چشم انداز", "چشم‌انداز", "جنگل", "طبیعت", "سبز"],
    "گرمایش/سرما": ["گرم", "بخاری", "پکیج", "شوفاژ", "سرد", "بخار"],
    "حشرات/پشه": ["پشه", "حشره", "مورچه", "سوسک", "جونده", "موذی"],
    "آشپزخانه و ظروف": ["آشپزخانه", "اشپزخانه", "ظروف", "یخچال", "اجاق", "گاز"],
    "اینترنت/آنتن": ["اینترنت", "آنتن", "وای فای", "وایفای", "وای فا"],
    "سر و صدا/همسایه": ["سر و صدا", "صدا", "همسایه", "شلوغ"],
    "قیمت و ارزش": ["قیمت", "گرون", "گران", "ارزون", "به صرفه", "بصرفه", "ارزش"],
}

for r in reviews:
    r["_norm"] = norm(r.get("متن_نظر") or "")

def hits(review, words):
    t = review["_norm"]
    return any(wd in t for wd in words)

results = {}
for theme, words in THEMES.items():
    c5 = sum(1 for r in star5 if hits(r, words))
    csub = sum(1 for r in sub5 if hits(r, words))
    clow = sum(1 for r in low3 if hits(r, words))
    results[theme] = {"star5": c5, "sub5": csub, "low3": clow, "total": c5 + csub}

# ---------- نقل‌قول‌های واقعی گلایه‌ها ----------
def quotes(theme_words, n=3, maxlen=160):
    out = []
    for r in sorted(low3, key=lambda r: r["_rating"]):
        t = (r.get("متن_نظر") or "").strip().replace("\n", " ")
        if any(wd in r["_norm"] for wd in theme_words) and len(t) > 30:
            out.append(f"[{r['_rating']:g}⭐ | اتاق {r['شناسه_اقامتگاه']} | {r.get('تاریخ_نظر','')[:10]}] {t[:maxlen]}…")
        if len(out) >= n:
            break
    return out

COMPLAINT_QUOTE_THEMES = {
    "مسیر دسترسی": THEMES["مسیر دسترسی"],
    "حشرات/پشه": THEMES["حشرات/پشه"],
    "سرویس بهداشتی/حمام": THEMES["سرویس بهداشتی/حمام"],
    "گرمایش/سرما": THEMES["گرمایش/سرما"],
    "اینترنت/آنتن": THEMES["اینترنت/آنتن"],
    "سر و صدا/همسایه": THEMES["سر و صدا/همسایه"],
}

lines = []
def w(s=""):
    lines.append(s)

w("## معدن‌کاوی 1,450 نظر (29 اتاق برتر)")
w()
w(f"- کل نظرها: {len(reviews)} | 5ستاره: {len(star5)} | زیر 5: {len(sub5)} | گلایه (<=3ستاره): {len(low3)}")
w(f"- سوگیری نمونه: نظرها فقط از 29 اتاق پرنظر/بالاامتیاز آمده — نمای کل بازار 395 کلبه نیست.")
w()
w("### فراوانی مضامین (تعداد نظرِ دربردارنده)")
w("| مضمون | در 5ستاره | در زیر5 | در گلایه(<=3) | سهم از کل |")
w("|---|---|---|---|---|")
for theme, c in sorted(results.items(), key=lambda kv: -kv[1]["total"]):
    w(f"| {theme} | {c['star5']} | {c['sub5']} | {c['low3']} | {round(c['total']*100/len(reviews))}٪ |")
w()
w("### نمونه نقل‌قول واقعی از گلایه‌های پرتکرار")
for theme, words in COMPLAINT_QUOTE_THEMES.items():
    w(f"**{theme}** (تکرار در نظرات <=3: {results[theme]['low3']})")
    for q in quotes(words):
        w(f"- {q}")
    w()
w("### خوانش روشی")
w("- فراوانی کلیدواژه‌ای؛ یک نظر می‌تواند چند مضمون داشته باشد؛ جمع ستون‌ها = تعداد نظرها نیست.")
w("- بدون تحلیل احساس خودکار — تفکیک 5ستاره/زیر5 به‌جای آن.")
w("- مجموع برای راستی‌آزمایی: هر عدد با شمارش مستقل csv بازتولید می‌شود.")

with open(os.path.join(ANA, "review_themes.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("\n".join(lines[:30]))
print("...\n[saved] review_themes.md")
