#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compute_past_revenue.py — محاسبه درآمد از snapshotهای رادار (روزهای گذشته)
=========================================================================

API جاجیگا فقط شب‌های آینده (از دیروز) رو می‌ده؛ از API نمی‌تونی روزهای
گذشته رو بازیابی کنی. اما snapshotهای روزانه رادار (data/radar/snapshots/*.json)
تاریخچه is_unavailable شب‌ها رو نگه می‌دارند.

الگوریتم — «آخرین snapshot معتبر برای هر تاریخ»:
  برای هر (room_id, date) که در بازه [PERIOD_START, PERIOD_END] باشد و
  تاریخش قبل از امروز باشد:
    - تمام snapshotها را بررسی می‌کنیم.
    - آخرین snapshot S که:
      (a) شامل آن date باشد، و
      (b) fetched_at آن >= date (snapshot در یا بعد از روز آن شب در دسترس باشد)
    وضعیت نهایی را می‌دهد.
    - اگر در snapshot S، is_unavailable=true باشد → رزرو گذشته ثابت شده.
    - اگر is_unavailable=false یا در هیچ snapshot معتبری نباشد → رزرو نشده.

  این روش artifact اولین شب را حذف می‌کند، چون:
    - در snapshot روز T، اولین شب (T-1) ممکن است artifact باشد.
    - ولی در snapshotهای بعدی (T+1، T+2)، T-1 همچنان بررسی می‌شود.
    - اگر T-1 در snapshot T+1 هم is_unavailable=true باشد → رزرو ثابت.
    - اگر در T+1 false باشد یا نباشد → artifact یا لغو شده.

ورودی:  data/radar/snapshots/*.json
خروجی: data/revenue/realized-seydkola-mordad-1405.json
"""
import json
import os
import glob
from datetime import date, datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
SNAPSHOT_DIR = os.path.join(ROOT, "data", "radar", "snapshots")
OUTPUT_DIR = os.path.join(ROOT, "data", "revenue")

COMMISSION_RATE = 0.12
PERIOD_START = date(2026, 7, 23)   # ۱ مرداد ۱۴۰۵
PERIOD_END = date(2026, 8, 22)      # ۳۱ مرداد ۱۴۰۵


def load_snapshots():
    """همه snapshotها را مرتب بر اساس تاریخ فایل بارگذاری می‌کند."""
    files = sorted(glob.glob(os.path.join(SNAPSHOT_DIR, "*.json")))
    snaps = []
    for f in files:
        try:
            data = json.load(open(f, encoding="utf-8"))
            fetched_at = data.get("fetched_at", "").split("T")[0]
            snaps.append({
                "date": os.path.basename(f).replace(".json", ""),
                "fetched_at": fetched_at,
                "rooms": data.get("rooms", {}),
            })
        except Exception as e:
            print(f"  [WARN] {f}: {e}", flush=True)
    return snaps


def compute_room(room_id, recs, today):
    """
    recs: لیست snapshotهای حاوی این room_id، مرتب از قدیمی به جدید.
    برای هر شب در بازه، آخرین snapshot معتبر (fetched_at >= date) را پیدا می‌کند.
    """
    meta = recs[-1]["rooms"][room_id].get("meta", {}) if recs else {}

    # تمام تاریخ‌های ممکنا از تمام snapshotهای این اتاق
    # برای هر snapshot، nights را می‌خوانیم
    # map: date_str -> {price, discount, weekend, holiday, peak, snap_index}
    # فقط آخرین snapshot معتبر برای هر تاریخ نگهداری می‌شود

    # ابتدا تمام شب‌ها را از تمام snapshotها جمع‌آوری می‌کنیم
    nights_by_date = {}  # date_str -> (snap_index, night_dict)
    for si, snap in enumerate(recs):
        nights = snap["rooms"][room_id].get("nights") or []
        fetched_at = snap["fetched_at"]
        for n in nights:
            d = n.get("date") or ""
            if not d:
                continue
            try:
                dd = date.fromisoformat(d[:10])
            except Exception:
                continue
            if dd < PERIOD_START or dd > PERIOD_END:
                continue
            if dd >= today:
                continue
            # فقط snapshotهایی که fetched_at >= date دارند معتبرند
            # (یعنی snapshot بعد از یا در روز همان شب)
            if fetched_at < d:
                continue
            # آخرین snapshot معتبر را نگه می‌داریم
            nights_by_date[d] = (si, n)

    booked = []
    for d, (si, n) in sorted(nights_by_date.items()):
        if not n.get("is_unavailable"):
            # در آخرین snapshot معتبر، آزاد است → رزرو نشد
            # (ممکن است قبلاً رزرو بوده باشد اما لغو شد)
            continue
        price = n.get("price") or 0
        disc = n.get("discount") or 0
        eff = round(price * (100 - disc) / 100) if disc else price
        booked.append({
            "date": d,
            "price": price,
            "effective_price": eff,
            "discount": disc,
            "weekend": bool(n.get("is_weekend")),
            "holiday": bool(n.get("is_holiday")),
            "peak": bool(n.get("is_peak")),
        })

    booked.sort(key=lambda x: x["date"])

    gross = sum(b["price"] for b in booked)
    gross_disc = sum(b["effective_price"] for b in booked)
    discount_total = gross - gross_disc
    commission = round(gross_disc * COMMISSION_RATE)
    net = gross_disc - commission

    return {
        "id": room_id,
        "title": meta.get("title", ""),
        "host_name": meta.get("host_name", ""),
        "host_id": meta.get("host_id", 0),
        "village": meta.get("village", ""),
        "booked": len(booked),
        "free": 0,
        "gross": gross,
        "gross_discounted": gross_disc,
        "discount_total": discount_total,
        "commission": commission,
        "net": net,
        "nights": booked,
    }


def main():
    snaps = load_snapshots()
    if not snaps:
        print("No snapshots found in", SNAPSHOT_DIR)
        return

    today = date.today()
    print(f"Loaded {len(snaps)} snapshots "
          f"({snaps[0]['fetched_at']} .. {snaps[-1]['fetched_at']})", flush=True)
    print(f"Computing past revenue for period {PERIOD_START} .. {min(PERIOD_END, today)}", flush=True)

    # ترتیب snapshotها از قدیمی به جدید
    # برای هر اتاق، لیست snapshotهای حاوی آن
    room_snaps = {}  # room_id -> [snap1, snap2, ...]
    for snap in snaps:
        for room_id in snap["rooms"]:
            room_snaps.setdefault(room_id, []).append(snap)

    results = []
    for room_id, recs in room_snaps.items():
        r = compute_room(room_id, recs, today)
        if r["booked"] > 0:
            results.append(r)

    results.sort(key=lambda r: r["net"], reverse=True)

    all_dates = sorted(n["date"] for r in results for n in r["nights"])
    if all_dates:
        range_label = f"{all_dates[0]} تا {all_dates[-1]} ۱۴۰۵"
    else:
        range_label = "---"

    output = {
        "realized_range": range_label,
        "rooms": results,
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_file = os.path.join(OUTPUT_DIR, "realized-seydkola-mordad-1405.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    n_rooms = len(results)
    n_nights = sum(r["booked"] for r in results)
    tot_net = sum(r["net"] for r in results)
    tot_gross = sum(r["gross_discounted"] for r in results)
    tot_disc = sum(r["discount_total"] for r in results)
    tot_comm = sum(r["commission"] for r in results)

    print(f"Rooms with past bookings: {n_rooms} | nights: {n_nights}", flush=True)
    print(f"  ناخالص: {tot_gross:,} | تخفیف: {tot_disc:,} | کمیسیون: {tot_comm:,} | خالص: {tot_net:,}", flush=True)
    print(f"Saved: {out_file}", flush=True)


if __name__ == "__main__":
    main()
