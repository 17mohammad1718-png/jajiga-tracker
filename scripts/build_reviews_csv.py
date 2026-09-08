#!/usr/bin/env python3
"""build_reviews_csv.py — خروجی سوم: reviews.csv
منبع: selected_reviews (API-first). ستون‌ها طبق پرامپت؛ بدون نام/اطلاعات شخصی مهمان.
"""
import csv, glob, json, os

ROOT = r"H:/projects/jajiga-tracker"
SR = os.path.join(ROOT, "data", "competitive", "selected_reviews")
OUT_DIR = os.path.join(ROOT, "exports", "competitive_2026-09-08")

COLS = ["شناسه_اقامتگاه", "تاریخ_نظر", "امتیاز", "متن_نظر", "پاسخ_میزبان", "تاریخ_پاسخ_میزبان", "منبع"]

roster = json.load(open(os.path.join(ROOT, "data", "competitive", "roster.json"), encoding="utf-8"))
main_titles = {e["id"]: e.get("title","") for e in roster["main"]}

rows = []
for p in sorted(glob.glob(os.path.join(SR, "*.json"))):
    if os.path.basename(p).startswith("_"): continue
    d = json.load(open(p, encoding="utf-8"))
    rid = d["room_id"]
    for r in d.get("reviews") or []:
        hr = r.get("host_reply") or {}
        if isinstance(hr, dict):
            reply = (hr.get("content") or "").strip()
            rdate = (hr.get("created_at") or "")[:10]
        else:
            reply, rdate = "", ""
        rows.append({
            "شناسه_اقامتگاه": rid,
            "تاریخ_نظر": (r.get("created_at") or "")[:10],
            "امتیاز": r.get("rating") if r.get("rating") is not None else "",
            "متن_نظر": (r.get("content") or "").replace("\r", " ").strip(),
            "پاسخ_میزبان": reply.replace("\r", " "),
            "تاریخ_پاسخ_میزبان": rdate,
            "منبع": d.get("source", ""),
        })

rows.sort(key=lambda x: (x["شناسه_اقامتگاه"], x["تاریخ_نظر"]), reverse=False)
out = os.path.join(OUT_DIR, "reviews.csv")
with open(out, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
    w.writeheader(); w.writerows(rows)
rooms = len({r["شناسه_اقامتگاه"] for r in rows})
print(f"reviews.csv: {len(rows)} rows from {rooms} rooms -> {out}")
