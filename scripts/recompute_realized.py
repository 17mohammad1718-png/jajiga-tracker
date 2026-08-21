#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""recompute_realized.py — محاسبه درآمد محقق‌شده (روزهای گذشته) از snapshotهای رادار
================================================================================
منبع: data/radar/snapshots/{YYYY-MM-DD}.json (اسنپ‌شات روزانه همه اتاق‌های رادار)
خروجی: data/revenue/realized-seydkola-mordad-1405.json

چرا لازمه:
    - API جاجیگا فقط شب‌های آینده رو میده (قدمی‌ترین = دیروز)؛ روزهای گذشته
      از خودِ API قابل بازیابی نیست.
    - اما اسنپ‌شات‌های روزانه رادار از ۲۰۲۶-۰۸-۰۸ ذخیره شدن و هر کدوم شامل
      nights (date, price, discount, is_unavailable) برای اتاق‌هاست.

قانون ضد-artifact (حیاتی):
    - اولین شب هر اسنپ‌شات همیشه is_unavailable=True است — آرتیفکت.
    - پس برای هر روز D، از «آخرین اسنپ‌شاتی» استفاده می‌کنیم که تاریخش > D
      (یعنی D براش گذشته است) → مقدار پایدار و غیر-آرتیفکت.
    - روزهایی که هنوز اسنپ‌شاتِ «بعد از خودشون» نیامده (مثلاً امروز) → رد میشن.

بازه خروجی: خودکار — از اولین اسنپ‌شات تا (آخرین اسنپ‌شات - ۱ روز).
    با داده فعلی: ۲۰۲۶-۰۸-۰۸ .. ۲۰۲۶-۰۸-۱۲ (۱۷ تا ۱۲ مرداد).

اتاق‌ها: همه اتاق‌های موجود در اسنپ‌شات‌ها (نه فقط کانفیگ رادار) — تا با
    فایل revenue فعلی (۳۳ اتاق) هم‌پوشانی داشته باشه. برای اتاق‌هایی که در
    اسنپ‌شات نیستن → رکورد خالی (booked=0).
کمیسیون: ۱۲٪ (فرض فعلی — هر بار تأیید شود).
"""
import json
import os
import sys
from datetime import date, datetime, timezone

try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from radar_common import ROOMS, LABELS, OWN_IDS, SHORT_LABELS
except Exception:
    ROOMS, LABELS, OWN_IDS, SHORT_LABELS = [], {}, set(), {}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
SNAPSHOT_DIR = os.path.join(ROOT, "data", "radar", "snapshots")
REVENUE_DIR = os.path.join(ROOT, "data", "revenue")
OUT_FILE = os.path.join(REVENUE_DIR, "realized-seydkola-mordad-1405.json")
PRICING_FILE = os.path.join(ROOT, "data", "pricing", "pricing-dataset.json")

COMMISSION_RATE = 0.12

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def load_snapshots():
    """همه اسنپ‌شات‌ها را می‌خواند → dict {date: {room_id: [nights]}}."""
    snaps = {}
    if not os.path.isdir(SNAPSHOT_DIR):
        return snaps
    for fn in sorted(os.listdir(SNAPSHOT_DIR)):
        if not fn.endswith(".json"):
            continue
        d = fn[:-5]
        try:
            gd = date.fromisoformat(d)
        except Exception:
            continue
        try:
            raw = json.load(open(os.path.join(SNAPSHOT_DIR, fn), encoding="utf-8"))
        except Exception:
            continue
        rooms = raw.get("rooms") or {}
        parsed = {}
        for rid_s, rdata in rooms.items():
            try:
                rid = int(rid_s)
            except Exception:
                rid = rid_s
            parsed[rid] = rdata.get("nights") or []
        snaps[gd] = parsed
    return snaps


def eff_price(price, discount):
    if not price:
        return 0
    if discount:
        return round(price * (100 - discount) / 100)
    return price


def compute_realized(snaps):
    """درآمد محقق‌شده را برای همه اتاق‌های اسنپ‌شات محاسبه می‌کند."""
    if not snaps:
        return [], None, None
    dates = sorted(snaps.keys())
    first, last = dates[0], dates[-1]
    # آخرین روز محقق‌شده = آخرین اسنپ‌شات - ۱ روز (تا artifact حذف شود)
    end_realized = last  # روزهای D با اسنپ‌شات > D معتبرند
    # روزهای محقق‌شده: از first تا (last - ۱)
    realized_days = []
    d = first
    while d < last:
        realized_days.append(d)
        d = date.fromordinal(d.toordinal() + 1)

    if not realized_days:
        return [], first, last

    # جمع‌آوری همه اتاق‌های دیده‌شده در اسنپ‌شات‌ها
    room_ids = set()
    for parsed in snaps.values():
        room_ids.update(parsed.keys())
    # ترتیب پایدار: اتاق‌های کانفیگ اول، بعد بقیه
    cfg_ids = [r["id"] for r in ROOMS]
    ordered = [rid for rid in cfg_ids if rid in room_ids]
    ordered += sorted(rid for rid in room_ids if rid not in cfg_ids)

    results = []
    for rid in ordered:
        booked = []
        for D in realized_days:
            # آخرین اسنپ‌شات با تاریخ > D (در لیست مرتب صعودی؛ آخرین مورد > D = معنادار)
            cand = None
            for sd in dates:
                if sd > D:
                    cand = sd
            if cand is None:
                continue
            nts = snaps[cand].get(rid) or []
            match = next((n for n in nts if n.get("date") == D.isoformat()), None)
            if not match:
                continue
            if not match.get("is_unavailable"):
                continue
            disc = match.get("discount") or 0
            price = match.get("price") or 0
            booked.append({
                "date": D.isoformat(),
                "price": price,
                "effective_price": eff_price(price, disc),
                "discount": disc,
                "weekend": bool(match.get("is_weekend")),
                "holiday": bool(match.get("is_holiday")),
                "peak": bool(match.get("is_peak")),
            })

        booked.sort(key=lambda x: x["date"])
        gross = sum(b["price"] or 0 for b in booked)
        gross_disc = sum(b["effective_price"] for b in booked)
        discount_total = gross - gross_disc
        commission = round(gross_disc * COMMISSION_RATE)
        net = gross_disc - commission

        results.append({
            "id": rid,
            "title": LABELS.get(rid, "") or f"اتاق {rid}",
            "own": bool(rid in OWN_IDS),
            "booked": len(booked),
            "gross": gross,
            "gross_discounted": gross_disc,
            "discount_total": discount_total,
            "commission": commission,
            "net": net,
            "range_start": realized_days[0].isoformat(),
            "range_end": realized_days[-1].isoformat(),
            "nights": booked,
        })

    return results, first, last


def load_titles():
    """عنوان دقیق‌تر از pricing-dataset (fallback LABELS)."""
    titles = {}
    try:
        for c in json.load(open(PRICING_FILE, encoding="utf-8")):
            if c.get("id"):
                titles[c["id"]] = c.get("title", "")
    except Exception:
        pass
    return titles


def main():
    snaps = load_snapshots()
    if not snaps:
        print("No snapshots found in data/radar/snapshots/")
        sys.exit(1)

    results, first, last = compute_realized(snaps)
    titles = load_titles()
    for r in results:
        r["title"] = titles.get(r["id"]) or r["title"]

    os.makedirs(REVENUE_DIR, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "radar snapshots",
        "commission_rate": COMMISSION_RATE,
        "snapshot_first": first.isoformat(),
        "snapshot_last": last.isoformat(),
        "realized_range": (
            f"{results[0]['range_start']}..{results[0]['range_end']}" if results else "—"
        ),
        "rooms": results,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    n_booked = sum(1 for r in results if r["booked"] > 0)
    tot_net = sum(r["net"] for r in results)
    print("=" * 60)
    print(f"Realized revenue: {len(results)} rooms | "
          f"range {payload['realized_range']} | commission {int(COMMISSION_RATE*100)}%")
    print(f"  rooms with bookings: {n_booked} | total net {tot_net:,}")
    print(f"Saved: {OUT_FILE}")


if __name__ == "__main__":
    main()
