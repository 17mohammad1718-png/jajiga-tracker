#!/usr/bin/env python3
"""
radar_tg.py — گزارش رادار رقبا به تلگرام (فرمت ایموجی — موبایل‌پسند)
=====================================================================
خروجی: متن گزارش روی stdout — کرون هرمس (no_agent, deliver=telegram) آن را
به چت کاربر می‌فرستد (خودکار هر ۶ ساعت / دستی با فایل نشانگر).

ساختار گزارش:
    1. HEADER — تاریخ امروز شمسی + روز هفته + ساعت آخرین به‌روزرسانی
    2. تغییرات ۲۴ ساعت — متن روایی با توضیح (رزرو/کنسلی/قیمت با تاریخ + روز هفته)
    3. گرید ۷ روز آینده — ایموجی‌ها + شمارنده پر + درصد اشغال هر اتاق
    4. خلاصه ۷ روز گذشته — آمار + برجسته‌ترین تغییرات
    5. درآمد تخمینی آینده — مجموع همه اقامتگاه‌ها + اقامتگاه خودی + ۳ برتر
    6. راهنما

هر رویداد تاریخ شمسی + روز هفته کامل می‌گیرد تا بدون نگاه به تقویم قابل
درک باشد. ترتیب ایموجی‌ها با U+200E (LRM) در متن RTL قفل شده است.
"""
import glob
import json
import os
import sys
from datetime import date, datetime, timedelta

from radar_common import ROOMS, SHORT_LABELS, OWN_IDS, JM, g2j, j_dm, j_dmy, weekday_idx, price_m, eff_price

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
SNAPSHOT_DIR = os.path.join(ROOT, "data", "radar", "snapshots")
REVENUE_DIR = os.path.join(ROOT, "data", "revenue")
COMMISSION_PCT = 12  # کمیسیون جاجیگا (طبق تنظیم کاربر) — فقط برای گزارش

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LRM = "\u200e"  # Left-to-Right Mark
E_BOOKED = "🔴"
E_FREE = "🟢"
E_HALF = "🟠"
E_PEAK = "💜"
E_NODATA = "⚪"

WD_FULL = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]


def wday(dstr):
    """'2026-08-09' → 'شنبه'"""
    return WD_FULL[weekday_idx(date.fromisoformat(dstr))]


def load_snapshot(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_snapshots():
    files = sorted(f for f in os.listdir(SNAPSHOT_DIR) if f.endswith(".json")) if os.path.isdir(SNAPSHOT_DIR) else []
    return files


def latest_snapshots():
    """(تاریخ آخرین اسنپ‌شات, اسنپ‌شات امروز, اسنپ‌شات قبلی)."""
    files = list_snapshots()
    if not files:
        print("NO_SNAPSHOTS — هنوز اسنپ‌شاتی نیست؛ اول fetch_radar.py اجرا شود.")
        sys.exit(0)
    today_file = files[-1]
    today_snap = load_snapshot(os.path.join(SNAPSHOT_DIR, today_file))
    prev_snap = None
    if len(files) >= 2:
        prev_snap = load_snapshot(os.path.join(SNAPSHOT_DIR, files[-2]))
    return today_file[:-5], today_snap, prev_snap


def room_by_date(snap):
    out = {}
    for rid, rdata in (snap or {}).get("rooms", {}).items():
        out[int(rid)] = {n["date"]: n for n in rdata.get("nights", [])}
    return out


def diff_events(today, today_snap, prev_snap):
    """رویدادهای تغییر بین دو اسنپ‌شات — فقط روزهای >= امروز.

    هر رویداد: (date_str, room_id, kind, text) با متن آماده فارسی.
    kinds: booked / freed / price_up / price_down
    """
    if not prev_snap:
        return []
    cur = room_by_date(today_snap)
    prev = room_by_date(prev_snap)
    events = []
    for room in ROOMS:
        rid = room["id"]
        cur_d = cur.get(rid, {})
        prev_d = prev.get(rid, {})
        label = SHORT_LABELS.get(rid, str(rid))
        for dstr in sorted(set(cur_d) & set(prev_d)):
            if dstr < today:
                continue  # گذشته: API آن را پر برمی‌گرداند → دیف کاذب
            c = cur_d[dstr]
            p = prev_d[dstr]
            c_book = bool(c.get("is_unavailable"))
            p_book = bool(p.get("is_unavailable"))
            if c_book and not p_book:
                pr = f" با قیمت {price_m(eff_price(c.get('price'), c.get('discount')))} میلیون" if c.get("price") else ""
                events.append((dstr, rid, "booked", f"🔴 {label} — {j_dm(dstr)} {wday(dstr)} رزرو شد{pr}"))
            elif not c_book and p_book:
                events.append((dstr, rid, "freed", f"🟢 {label} — {j_dm(dstr)} {wday(dstr)} آزاد شد (کنسلی)"))
            c_price = eff_price(c.get("price"), c.get("discount"))
            p_price = eff_price(p.get("price"), p.get("discount"))
            if c_price != p_price and c_price and p_price:
                diffM = (c_price - p_price) / 1_000_000
                kind = "price_up" if diffM > 0 else "price_down"
                events.append((dstr, rid, kind, label, p_price, c_price))
    events.sort(key=lambda e: (e[0], e[1]))
    return events


def price_run_label(group, kind):
    """یک خط برای گروه تغییرات قیمتی پشت‌سرهم مشابه (همان اتاق، همان تغییر، روزهای متوالی):
    📈 لیلا — قیمت 28 تا 29 مرداد (چهارشنبه تا پنجشنبه): 3.7 ← 4.7 میلیون"""
    arrow = "📈" if kind == "price_up" else "📉"
    label = group[0][3]
    frm, to = group[0][4], group[0][5]
    start, end = group[0][0], group[-1][0]
    j1, j2 = j_dm(start), j_dm(end)
    if start == end:
        dsp = f"{j1} {wday(start)}"
    elif j1.split()[1] == j2.split()[1]:
        dsp = f"{j1.split()[0]} تا {j2} ({wday(start)} تا {wday(end)})"
    else:
        dsp = f"{j1} تا {j2} ({wday(start)} تا {wday(end)})"
    return f"{arrow} {label} — قیمت {dsp}: {price_m(frm)} ← {price_m(to)} میلیون"


def render_events(events):
    """گروه‌بندی تغییرات قیمتی پشت‌سرهم مشابه → هر گروه یک خط، بقیه همان‌طور."""
    lines = []
    i, n = 0, len(events)
    while i < n:
        e = events[i]
        if e[2] in ("booked", "freed"):
            lines.append(e[3])
            i += 1
            continue
        group = [e]
        j = i + 1
        same = j < n and (events[j][1] == e[1] and events[j][2] == e[2]
                          and events[j][4] == e[4] and events[j][5] == e[5])
        while j < n and same and (date.fromisoformat(events[j][0]) - date.fromisoformat(group[-1][0])).days == 1:
            group.append(events[j])
            j += 1
            if j < n:
                same = (events[j][1] == e[1] and events[j][2] == e[2]
                        and events[j][4] == e[4] and events[j][5] == e[5])
        lines.append(price_run_label(group, e[2]))
        i = j
    return lines


def narrative_diff(today, today_snap, prev_snap):
    """متن روایی تغییرات ۲۴ ساعت — توضیح می‌دهد چه اتفاقی افتاده (تغییرات قیمتی مشابه پشت‌سرهم گروه‌بندی می‌شود)."""
    events = diff_events(today, today_snap, prev_snap)
    if not events:
        return "⚪ نسبت به دیروز تغییری ثبت نشد — وضعیت مثل قبل است."
    booked = sum(1 for e in events if e[2] == "booked")
    freed = sum(1 for e in events if e[2] == "freed")
    price = sum(1 for e in events if e[2].startswith("price"))
    head = f"از دیروز {len(events)} تغییر ثبت شده:"
    if booked and freed and price:
        head = f"از دیروز {len(events)} تغییر ثبت شده ({booked} رزرو جدید، {freed} کنسلی، {price} تغییر قیمت):"
    elif booked:
        head = f"از دیروز {booked} رزرو جدید ثبت شده:"
    elif freed:
        head = f"از دیروز {freed} مورد آزاد شدن (کنسلی) ثبت شده:"
    lines = [head]
    lines.extend(render_events(events))
    return "\n".join(lines)


def week_summary(today, today_snap):
    """خلاصه روایی ۷ روز گذشته + آمار کل."""
    files = list_snapshots()
    if len(files) < 2:
        return None, None
    target = date.fromisoformat(today) - timedelta(days=7)
    chosen = None
    for fn in files:
        fdate = date.fromisoformat(fn[:-5])
        if fdate <= target:
            chosen = (fn, fdate)
    if chosen is None:
        chosen = (files[0], date.fromisoformat(files[0][:-5]))
    if chosen[0] == files[-1]:
        return None, None
    prev = load_snapshot(os.path.join(SNAPSHOT_DIR, chosen[0]))
    events = diff_events(today, today_snap, prev)
    return chosen[1].isoformat(), events


def day_emoji(n, prev_n):
    if not n:
        return E_NODATA
    if n.get("is_unavailable"):
        return E_BOOKED
    if n.get("is_peak") or n.get("is_holiday"):
        return E_PEAK
    if prev_n and prev_n.get("is_unavailable"):
        return E_HALF
    return E_FREE


def grid_report(today, today_snap, days_ahead=7):
    """گرید ۷ روز آینده: هر اتاق یک خط ایموجی + شمارنده پر + درصد اشغال."""
    data = room_by_date(today_snap)
    start = date.fromisoformat(today) + timedelta(days=1)
    dates = [start + timedelta(days=i) for i in range(days_ahead)]
    end = dates[-1]

    lines = [f"📅 **وضعیت ۷ روز آینده** ({j_dm(start.isoformat())} تا {j_dm(end.isoformat())})", ""]
    
    # ردیف روز هفته بالای گرید
    wd_row = [f"{LRM}{WD_FULL[weekday_idx(d)][:3]}" for d in dates]
    date_row = [f"{LRM}{j_dm(d.isoformat()).split(' ')[0]}" for d in dates]
    lines.append("      " + "  ".join(wd_row))
    lines.append("      " + "  ".join(date_row))
    lines.append("")
    
    for room in ROOMS:
        rid = room["id"]
        cd = data.get(rid, {})
        cells = []
        for i, d in enumerate(dates):
            n = cd.get(d.isoformat())
            prev_n = cd.get((d - timedelta(days=1)).isoformat())
            cells.append(day_emoji(n, prev_n))
        full = sum(1 for c in cells if c == E_BOOKED)
        pct = round(full * 100 / days_ahead)
        label = SHORT_LABELS.get(rid, str(rid))
        star = " ✨" if room.get("own") else ""
        lines.append(f"{LRM}{label}{star}   {' '.join(cells)}   {full}/{days_ahead} ({pct}٪)")
    return "\n".join(lines)


def revenue_section():
    """درآمد تخمینی آینده از آخرین فایل data/revenue/*.json (همه اقامتگاه‌ها)."""
    files = sorted(glob.glob(os.path.join(REVENUE_DIR, "*.json")))
    if not files:
        return None
    try:
        items = json.load(open(files[-1], encoding="utf-8"))
    except Exception:
        return None
    if not items:
        return None

    total_booked = sum(x.get("booked") or 0 for x in items)
    total_gross = sum(x.get("gross") or 0 for x in items)
    total_net = sum(x.get("net") or 0 for x in items)
    total_commission = sum(x.get("commission") or 0 for x in items)

    def fmt_m(v):
        return f"{v/1_000_000:,.1f}"

    own_ids = OWN_IDS or {3297585}
    own = next((x for x in items if x.get("id") in own_ids), None)
    ranked = sorted(items, key=lambda x: x.get("gross") or 0, reverse=True)

    lines = ["💰 **درآمد تخمینی آینده**", ""]
    lines.append(
        f"مجموع {len(items)} اقامتگاه: {total_booked} شب رزرو · "
        f"ناخالص {fmt_m(total_gross)}M · کمیسیون {fmt_m(total_commission)}M · "
        f"خالص {fmt_m(total_net)}M"
    )
    if own:
        lines.append(
            f"• **خودت ({own.get('title', '')})**: {own.get('booked')} شب · "
            f"ناخالص {fmt_m(own.get('gross') or 0)}M · خالص {fmt_m(own.get('net') or 0)}M"
        )
    lines.append("")
    lines.append("**۳ اقامتگاه برتر (ناخالص):**")
    for i, x in enumerate(ranked[:3], 1):
        lines.append(f"{i}. {x.get('title', '')} — {x.get('booked')} شب · {fmt_m(x.get('gross') or 0)}M")
    return "\n".join(lines)


def main():
    days_ahead = 7
    if "--days" in sys.argv:
        i = sys.argv.index("--days")
        days_ahead = int(sys.argv[i + 1])

    today, today_snap, prev_snap = latest_snapshots()
    jy, jm, jd = g2j(*map(int, today.split("-")))
    today_fa = f"{jd} {JM[jm-1]} {jy}"
    fa = today_snap.get("fetched_at") or ""
    upd = ""
    if fa:
        try:
            upd = " · " + datetime.fromisoformat(fa).astimezone().strftime("%H:%M")
        except Exception:
            pass

    out = [f"🛰️ **رادار رقبا — {today_fa} ({wday(today)}){upd}**"]

    # --- گرید ۷ روز آینده ---
    out.append("")
    out.append(grid_report(today, today_snap, days_ahead))

    # --- دلتا: تغییرات از اسنپ‌شات قبلی ---
    events = diff_events(today, today_snap, prev_snap)
    out.append("")
    if events:
        booked = sum(1 for e in events if e[2] == "booked")
        freed = sum(1 for e in events if e[2] == "freed")
        price = sum(1 for e in events if e[2].startswith("price"))
        lines = render_events(events)
        out.append(f"**📝 تغییرات از گزارش قبل ({len(events)} تغییر در {len(lines)} خط):**")
        if booked or freed or price:
            parts = []
            if booked: parts.append(f"{booked} رزرو")
            if freed: parts.append(f"{freed} کنسلی")
            if price: parts.append(f"{price} تغییر قیمت")
            out.append(" · ".join(parts))
        for line in lines:
            out.append(line)
    else:
        out.append("**📝 تغییرات از گزارش قبل:** ⚪ تغییری نیست")

    # --- درآمد تخمینی ---
    rev = revenue_section()
    if rev:
        out.append("")
        out.append(rev)

    out.append("")
    out.append(f"{E_FREE} خالی · {E_BOOKED} پر · {E_HALF} نیمه‌پر (روز تحویل) · {E_PEAK} پیک/تعطیل")

    print("\n".join(out))


if __name__ == "__main__":
    main()
