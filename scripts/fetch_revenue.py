#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_revenue.py — به‌روزرسانی داده داشبورد درآمد تخمینی از API جاجیگا
=========================================================================
ورودی: data/revenue/seydkola-mordad-1405.json (اتاق‌ها + عنوان)
خروجی: همان فایل با داده تازه — فقط شب‌های رزروشده در بازه پنجره

بازه: مرداد ۱۴۰۵ = 2026-07-23 (۱ مرداد) .. 2026-08-22 (۳۱ مرداد)

قوانین (مستند jajiga-revenue-estimation):
    - منبع: api.jajiga.com/api/nights?room_id={id}  (بدون auth)
    - پاسخ دیکت {"room": {...}, "nights": [...]} است؛ ~۱۰۶ شب از دیروز
    - رزرو = is_unavailable و today <= date <= end پنجره
    - قانون طلایی: روزهای گذشته (date < today) هرگز «پر» حساب نمی‌شوند
      (اولین شبِ پنجره در API همیشه is_unavailable=true — آرتیفکت است)
    - تخفیف هر شب اعمال می‌شود: effective_price = price × (1 − discount/100)
    - کمیسیون ۱۲٪ (فرض فعلی کاربر — قبل از استناد تأیید شود)
    - فچ موازی (۴ همزمان) + retry نمایی + jitter — مثل fetch_radar.py
"""
import json
import os
import random
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
REVENUE_FILE = os.path.join(ROOT, "data", "revenue", "seydkola-mordad-1405.json")
PRICING_FILE = os.path.join(ROOT, "data", "pricing", "pricing-dataset.json")
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
DELAY_MIN, DELAY_MAX = 0.4, 1.2
MAX_ATTEMPTS = 4
CONCURRENCY = 4
COMMISSION_RATE = 0.12
MANUAL_BLOCKS = {}  # room_id_str -> set of ISO dates (بارگذاری در main)

# پنجره مرداد ۱۴۰۵ (۱ مرداد = 2026-07-23، ۳۱ مرداد = 2026-08-22)
PERIOD_START = date(2026, 7, 23)
PERIOD_END = date(2026, 8, 22)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def load_rooms():
    """اتاق‌ها از فایل درآمد فعلی؛ اگر نبود از pricing-dataset (سیدکلا)."""
    if os.path.exists(REVENUE_FILE):
        data = json.load(open(REVENUE_FILE, encoding="utf-8"))
        if isinstance(data, list) and data:
            return data
    # fallback: ساخت از pricing dataset — فقط سیدکلا
    rooms = []
    try:
        for c in json.load(open(PRICING_FILE, encoding="utf-8")):
            if c.get("village") == "سیدکلا" and c.get("id"):
                rooms.append({"id": c["id"], "title": c.get("title", "")})
    except Exception:
        pass
    return rooms


def fetch_nights(room_id):
    """تقویم کامل یک اتاق. Returns list of night dicts."""
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


def eff_price(price, discount):
    if not price:
        return 0
    if discount:
        return round(price * (100 - discount) / 100)
    return price


def load_manual_blocks():
    """روزهای «بسته میزبان» (غیرمشتری) — از درآمد مستثنی می‌شوند."""
    try:
        data = json.load(open(MANUAL_BLOCKS_FILE, encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for rid, dates in (data or {}).items():
        if isinstance(dates, list):
            out[str(rid)] = set(d for d in dates if isinstance(d, str))
    return out


def compute_room(rec):
    """فچ + محاسبه درآمد یک اتاق. Returns updated record (یا None در خطا)."""
    rid = rec["id"]
    try:
        nights = fetch_nights(rid)
    except Exception as e:
        print(f"  [ERR] {rid} | {str(e)[:80]}", flush=True)
        return None

    today = date.today()
    blocked_dates = MANUAL_BLOCKS.get(str(rid), set())
    booked = []
    for n in nights:
        d = n.get("date")
        if not d:
            continue
        try:
            dd = date.fromisoformat(d)
        except Exception:
            continue
        # قانون طلایی: گذشته هرگز پر حساب نمی‌شود
        if dd < today or dd > PERIOD_END:
            continue
        if not n.get("is_unavailable"):
            continue
        if d in blocked_dates:
            continue  # بسته میزبان (غیرمشتری) — درآمد ندارد
        disc = n.get("discount") or 0
        booked.append({
            "date": d,
            "price": n.get("price"),
            "effective_price": eff_price(n.get("price"), disc),
            "discount": disc,
            "weekend": bool(n.get("is_weekend")),
            "holiday": bool(n.get("is_holiday")),
            "peak": bool(n.get("is_peak")),
        })

    booked.sort(key=lambda x: x["date"])
    gross = sum(b["price"] or 0 for b in booked)
    gross_disc = sum(b["effective_price"] for b in booked)
    discount_total = gross - gross_disc
    commission = round(gross_disc * COMMISSION_RATE)
    net = gross_disc - commission
    window_days = (PERIOD_END - today).days + 1
    free = max(window_days - len(booked), 0)

    return {
        "id": rid,
        "title": rec.get("title", ""),
        "booked": len(booked),
        "free": free,
        "gross": gross,
        "gross_discounted": gross_disc,
        "discount_total": discount_total,
        "commission": commission,
        "net": net,
        "nights": booked,
    }


def main():
    global MANUAL_BLOCKS
    MANUAL_BLOCKS = load_manual_blocks()
    rooms = load_rooms()
    if not rooms:
        print("No rooms — create data/revenue/seydkola-mordad-1405.json first.")
        sys.exit(1)
    print(f"Revenue rooms: {len(rooms)} | window {today_str()} .. {PERIOD_END} | "
          f"commission {int(COMMISSION_RATE*100)}%", flush=True)

    results = {}
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futures = {ex.submit(compute_room, rec): rec["id"] for rec in rooms}
        for fut in as_completed(futures):
            rid = futures[fut]
            updated = fut.result()
            if updated:
                results[rid] = updated
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    # حفظ ترتیب قبلی؛ اتاق‌های ناموفق دست‌نخورده می‌مانند (داده قدیمی حفظ شود)
    out = []
    ok = 0
    for rec in rooms:
        rid = rec["id"]
        if rid in results:
            out.append(results[rid])
            ok += 1
        else:
            out.append(rec)

    os.makedirs(os.path.dirname(REVENUE_FILE), exist_ok=True)
    with open(REVENUE_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    n_booked = sum(1 for r in out if r.get("booked"))
    tot_net = sum(r.get("net", 0) for r in out)
    print("=" * 60)
    print(f"Revenue fetch: {ok}/{len(rooms)} OK | {n_booked} rooms with bookings | "
          f"total net {tot_net:,}")
    print(f"Saved: {REVENUE_FILE}")


def today_str():
    return date.today().isoformat()


if __name__ == "__main__":
    main()
