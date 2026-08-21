#!/usr/bin/env python3
"""
build_radar_dashboard.py — ساخت داشبورد رادار رقبا (تک‌فایل HTML)
=================================================================
ورودی: data/radar/{room_id}.json  (خروجی fetch_radar.py)
خروجی: competitor-radar.html

نما:
    - جدول گرید: هر ردیف یک اتاق (کلبه خود کاربر اول + نشان «من»)،
      هر ستون یک روز از ماه جاری + ماه بعد شمسی
    - سربرگ ماه (colspan) + روز هفته واقعی روی هر ستون
    - رنگ سلول: پر/خالی/نیمه‌پر/پیک/تعطیل/آخر هفته/گذشته/بدون داده
    - tooltip هر سلول: تاریخ شمسی، قیمت، تخفیف، نوع روز
    - ستون‌های متریک: اشغال ۳۰/۶۰/۹۰ روز، میانگین قیمت شب، شب‌های تخفیف‌دار
    - مدال طلا/نقره/برنز برای ۳ اتاق با بیشترین اشغال ۳۰ روز
"""
import json
import os
import re
import sys
import base64
import io
from datetime import date, timedelta

from radar_common import eff_price, load_config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# xlsx-js-style (فورک SheetJS با پشتیبانی استایل در خروجی) — برای تولید فایل اکسل رنگی در مرورگر
XLSX_CDN = "https://cdn.jsdelivr.net/npm/xlsx-js-style@1.2.0/dist/xlsx.min.js"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
RADAR_DIR = os.path.join(ROOT, "data", "radar")
OUT = os.path.join(ROOT, "competitor-radar.html")

JM = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند']
# روز هفته (شنبه=0 ... جمعه=6) — ستون تقویم ایرانی
WD = ['ش','ی','د','س','چ','پ','ج']

def g2j(gy, gm, gd):
    gdm = [0,31,59,90,120,151,181,212,243,273,304,334]
    gy2 = gy + 1 if gm > 2 else gy
    d = 355666 + 365*gy + (gy2+3)//4 - (gy2+99)//100 + (gy2+399)//400 + gd + gdm[gm-1]
    jy = -1595 + 33*(d//12053); d %= 12053
    jy += 4*(d//1461); d %= 1461
    if d > 365:
        jy += (d-1)//365; d = (d-1)%365
    if d < 186:
        jm = 1 + d//31; jd = 1 + d%31
    else:
        jm = 7 + (d-186)//30; jd = 1 + (d-186)%30
    return jy, jm, jd

def jalali_str(dstr):
    y, m, d = map(int, dstr.split('-'))
    jy, jm, jd = g2j(y, m, d)
    return f"{jd} {JM[jm-1]} {jy}"

def weekday_idx(d):
    """شنبه=0 ... جمعه=6"""
    return (d.weekday() + 2) % 7

def month_days(jy, jm):
    """همه روزهای میلادیِ ماه شمسی (jy, jm) — با اسکن اطراف امروز."""
    days = []
    for off in range(-60, 130):
        d = date.today() + timedelta(days=off)
        y, m, _ = g2j(d.year, d.month, d.day)
        if y == jy and m == jm:
            days.append(d)
    return sorted(days)

def farvardin1(jy):
    """تاریخ میلادیِ ۱ فروردین سال شمسی jy (روی لنگر ۱/۱/۱۴۰۵ = 2026-03-21)."""
    anchor_jy, anchor_d = 1405, date(2026, 3, 21)
    est = anchor_d + timedelta(days=round((jy - anchor_jy) * 365.2422))
    for off in range(-40, 41):
        d = est + timedelta(days=off)
        if g2j(d.year, d.month, d.day)[:2] == (jy, 1):
            return d
    raise ValueError(f"فروردین سال {jy} پیدا نشد")

def jalali_year_months(jy):
    """۱۲ ماهِ سال شمسی jy بهصورت [(y, m, days)] — بدون منطق کبیسه (اسکن روزبهروز)."""
    months = []
    d = farvardin1(jy)
    for _ in range(378):  # یک سال شمسی حداکثر ۳۶۶ روز + یک روز اطمینان
        y, m, jd = g2j(d.year, d.month, d.day)
        if y != jy:
            break
        if not months or months[-1][1] != m:
            months.append((y, m, []))
        months[-1][2].append(d)
        d += timedelta(days=1)
    return months


def build():
    today = date.today()

    # شروع محاسبه درآمد — از کانفیگ رادار؛ اگر نبود امروز
    cfg = load_config()
    rev_start_str = cfg.get("revenue_start", today.isoformat())
    try:
        REVENUE_START = date.fromisoformat(rev_start_str)
    except Exception:
        REVENUE_START = today

    jy, jm, _ = g2j(today.year, today.month, today.day)

    # پنجره ثابت: دیروز (۱ روز گذشته برای مرجع) + امروز + ۴۴ روز آینده = همیشه ۴۵ روز جلوتر
    days_flat = [today + timedelta(days=off) for off in range(-1, 45)]
    months = []  # گروه‌بندی شمسی همان پنجره برای سربرگ ماه‌ها
    for d in days_flat:
        gy, gm, _ = g2j(d.year, d.month, d.day)
        if not months or months[-1][0] != gy or months[-1][1] != gm:
            months.append([gy, gm, [d]])
        else:
            months[-1][2].append(d)

    # ---------- بارگذاری + محاسبه متریک ----------
    rooms = []
    for fn in sorted(os.listdir(RADAR_DIR)):
        if not fn.endswith('.json') or fn == 'snapshots':
            continue
        rec = json.load(open(os.path.join(RADAR_DIR, fn), encoding='utf-8'))
        if not rec.get('nights'):
            continue
        rec['by_date'] = {n['date']: n for n in rec['nights']}
        ds = sorted(rec['by_date'])
        rec['first_date'] = ds[0] if ds else None

        occ = {}
        for win in (30, 60, 90):
            total = unav = 0
            for off in range(win):
                n = rec['by_date'].get((today + timedelta(days=off + 1)).isoformat())
                if n is None:
                    continue
                total += 1
                if n.get('is_unavailable'):
                    unav += 1
            occ[win] = round(unav / total * 100) if total else 0
        rec['occ'] = occ

        prices = [eff_price(n['price'], n.get('discount')) for off in range(90)
                  if (n := rec['by_date'].get((today + timedelta(days=off + 1)).isoformat())) and n.get('price')]
        rec['avg_price_90'] = round(sum(prices) / len(prices)) if prices else None
        rec['discount_days'] = sum(1 for n in rec['nights'] if n.get('discount'))
        rec['peak_days'] = sum(1 for n in rec['nights'] if n.get('is_peak'))
        rooms.append(rec)

    # گروه‌بندی میزبان‌ها: اتاق‌های هم‌میزبان کنار هم؛ اول کلبه‌های خود کاربر («من»)
    def _own(rec):
        return bool((rec.get('meta') or {}).get('own'))
    def _hkey(rec):
        m = rec.get('meta') or {}
        return (str(m.get('host_id') or ''), str(m.get('host_name') or ''))
    own_rooms = [r for r in rooms if _own(r)]
    others = [r for r in rooms if not _own(r)]
    host_order, groups = [], {}
    for r in others:
        k = _hkey(r)
        if k not in groups:
            groups[k] = []
            host_order.append(k)
        groups[k].append(r)
    rooms = own_rooms + [rr for k in host_order for rr in groups[k]]

    # مدال‌ها: ۳ اتاق با بیشترین اشغال ۳۰ روز (خود کاربر علامت «من» می‌گیرد)
    ranked = sorted(rooms, key=lambda r: r['occ'][30], reverse=True)
    medals = {ranked[i]['room_id']: ['🥇','🥈','🥉'][i] for i in range(min(3, len(ranked)))}

    # ---------- ادغام شب‌های گذشته از snapshotها در by_date ----------
    # شب‌های سپری‌شده از REVENUE_START تا دیروز از اسنپ‌شات‌های روزانه می‌آیند
    # تا جدول تخمین درآمد از ۱۷ مرداد به بعد کامل باشد
    snap_dir = os.path.join(RADAR_DIR, 'snapshots')
    trust_for_rev = {}  # date -> {room_id_str: night_dict}
    first_observed = {}
    for sf in sorted(os.listdir(snap_dir)):
        if not sf.endswith('.json'):
            continue
        try:
            snap = json.load(open(os.path.join(snap_dir, sf), encoding='utf-8'))
        except Exception:
            continue
        fa = str(snap.get('fetched_at') or '')
        try:
            snap_date = date.fromisoformat(fa[:10])
        except Exception:
            snap_date = today
        artifact_yesterday = (snap_date - timedelta(days=1)).isoformat()
        for rid, rdata in (snap.get('rooms') or {}).items():
            if str(rid) not in first_observed:
                first_observed[str(rid)] = snap_date.isoformat()
            nights = rdata.get('nights') or []
            for n in nights:
                nd = n['date']
                # فقط روزهای قبل از امروز، بعد از REVENUE_START، نه آرتیفکت دیروز
                if REVENUE_START.isoformat() <= nd < today.isoformat() and nd != artifact_yesterday:
                    trust_for_rev.setdefault(nd, {})[str(rid)] = n

    # ادغام در by_date هر اتاق
    for rec in rooms:
        rid_str = str(rec['room_id'])
        for dstr in sorted(trust_for_rev):
            n = trust_for_rev[dstr].get(rid_str)
            if n and n.get('is_unavailable'):
                rec['by_date'][dstr] = n

    # ---------- تخمین درآمد میزبان‌ها (شب‌های پر از ۱۷ مرداد به بعد) ----------
    # جمع‌بندی در مرورگر انجام می‌شود تا «تاریخ محاسبه درآمد» قابل تنظیم باشد:
    # داده‌ی خامِ هر اتاق (شب‌های پرِ آینده) داخل HTML می‌رود و با کلیک روی
    # چیپِ «تا تاریخ»، جاوااسکریپت جدول را بدون refetch دوباره حساب می‌کند.
    COMMISSION_RATE = 0.12
    def esc(s):
        return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    rev_rooms = []
    rev_horizon = today
    for rec in rooms:
        meta = rec.get('meta') or {}
        rid = rec['room_id']
        nights = []
        for dstr in sorted(rec['by_date']):
            if dstr < REVENUE_START.isoformat():
                continue  # فقط از ۱۷ مرداد به بعد
            n = rec['by_date'][dstr]
            if n.get('is_manual_block'):
                continue  # بسته میزبان (غیرمشتری) — درآمد ندارد
            if not n.get('is_unavailable'):
                continue
            dd = date.fromisoformat(dstr)
            if dd > rev_horizon:
                rev_horizon = dd
            price = n.get('price') or 0
            disc = n.get('discount') or 0
            eff = round(price * (100 - disc) / 100) if disc else price
            nights.append({
                'd': dstr,
                'p': eff,
                'b': price,
                'dc': disc,
                'w': bool(n.get('is_weekend')),
                'h': bool(n.get('is_holiday')),
                'k': bool(n.get('is_peak')),
            })
        rev_rooms.append({
            'id': rid,
            'title': esc(meta.get('title') or f'اتاق {rid}'),
            'village': meta.get('village') or '—',
            'host_name': esc(meta.get('host_name') or '—'),
            'host_id': str(meta.get('host_id') or ''),
            'own': bool(meta.get('own')),
            'nights': nights,
        })

    # «دوره محاسبه درآمد»: از تاریخ و تا تاریخ — هر دو قابل تنظیم (همه آینده)
    def month_end_date(jy, jm):
        md = month_days(jy, jm)
        return md[-1] if md else None

    chip_months = []  # (jalali_year, jalali_month, end_date)
    cur_y, cur_m = g2j(today.year, today.month, today.day)[:2]
    hor_y, hor_m = g2j(rev_horizon.year, rev_horizon.month, rev_horizon.day)[:2]
    guard = 0
    while (cur_y, cur_m) <= (hor_y, hor_m) and guard < 12:
        guard += 1
        endd = month_end_date(cur_y, cur_m)
        if endd and endd >= today:
            chip_months.append((cur_y, cur_m, endd))
        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1

    # پیش‌فرض = ۱۷ مرداد (شروع محاسبه درآمد) تا انتهای پنجره رادار
    default_start = REVENUE_START.isoformat()
    default_end = days_flat[-1].isoformat() if days_flat else rev_horizon.isoformat()

    # داده تقویم شمسی: کل سال جاری (ناوبری کامل ماه‌ها در پاپ‌آپ تقویم)
    cal_year = g2j(today.year, today.month, today.day)[0]
    rev_cal = []
    for y, m, days in jalali_year_months(cal_year):
        rev_cal.append({
            'y': y, 'm': m, 'name': JM[m-1],
            'days': [{'g': d.isoformat(), 'jd': g2j(d.year, d.month, d.day)[2],
                      'wd': weekday_idx(d)} for d in days],
        })

    # چیپ‌های دوره: «کل ماه» برای هر ماهِ در دسترس + «همه‌ی داده»
    rev_chips = []
    for y, m, endd in chip_months:
        md = month_days(y, m)
        first = next((d for d in md if d >= REVENUE_START), None)
        if first is None:
            continue
        if (y, m) == (hor_y, hor_m) and rev_horizon < endd:
            endd = rev_horizon
        rev_chips.append({'start': first.isoformat(), 'end': endd.isoformat(), 'label': f'کل {JM[m-1]}'})
    rev_chips.append({'start': default_start, 'end': rev_horizon.isoformat(), 'label': 'همه‌ی داده'})

    chips_html = ''.join(
        f"<button class='rc-chip' data-start='{c['start']}' data-end='{c['end']}'>{c['label']}</button>"
        for c in rev_chips
    )

    rev_rooms_json = json.dumps(rev_rooms, ensure_ascii=False)
    rev_ends_json = json.dumps({
        'today': today.isoformat(),
        'min': REVENUE_START.isoformat(),
        'max': rev_horizon.isoformat(),
        'default_start': default_start,
        'default_end': default_end,
        'months': rev_cal,
        'chips': rev_chips,
    }, ensure_ascii=False)

    # مجموع خالصِ پیش‌فرض (پنجره فعلی) برای برچسب اولیه — JS هم‌ارزش را می‌سازد
    tot_rev_net = 0
    for r in rev_rooms:
        gross = sum(n['p'] for n in r['nights'] if n['d'] <= default_end)
        tot_rev_net += gross - round(gross * COMMISSION_RATE)

    # روزهای تعطیل (سراسری تقویم) + مرز هفته/ماه برای خط‌های جداکننده
    holiday_dates = set()
    for rec in rooms:
        for dstr, n in rec['by_date'].items():
            if n.get('is_holiday'):
                holiday_dates.add(dstr)
    month_start_set = {days[0].isoformat() for _, _, days in months}

    def col_extras(d):
        """کلاس‌های اضافی ستون: شروع هفته (wb) و شروع ماه (mb).

        خط شروع ماه (mb) روی اولین ستون جدول زده نمی‌شود — آنجا لبه جدول
        است و خط اضافه فقط شلوغی می‌سازد؛ مرز واقعی بین دو ماه همان خط
        اول ماه دوم است که پایان ماه اول و شروع ماه دوم را جدا می‌کند.
        """
        cs = []
        if weekday_idx(d) == 0:   # شنبه = شروع هفته
            cs.append('wb')
        if d.isoformat() in month_start_set and d.isoformat() != days_flat[0].isoformat():
            cs.append('mb')
        return cs

    def cell_class(rec, d):
        if d.isoformat() < today.isoformat():
            return 'past'
        n = rec['by_date'].get(d.isoformat())
        if n is None:
            return 'nodata'
        if n.get('is_manual_block'):
            return 'blocked'
        if n.get('is_unavailable'):
            return 'booked'
        prev = rec['by_date'].get((d - timedelta(days=1)).isoformat())
        if prev and prev.get('is_unavailable'):
            return 'half'
        if n.get('is_peak'):
            return 'peak'
        if n.get('is_weekend'):
            return 'weekend'
        return 'free'

    def cell_html(rec, d):
        n = rec['by_date'].get(d.isoformat())
        extra = (' ' + ' '.join(col_extras(d))) if col_extras(d) else ''
        if n is None:
            return f"<td class='c nodata{extra}'><span class='dn'>{g2j(d.year, d.month, d.day)[2]}</span></td>"
        parts = [jalali_str(d.isoformat())]
        eff = eff_price(n.get('price'), n.get('discount'))
        if n.get('price'):
            if n.get('discount'):
                parts.append(f"قیمت پایه: {n['price']:,}")
                parts.append(f"تخفیف: {n['discount']}٪")
                parts.append(f"قیمت نهایی: {eff:,}")
            else:
                parts.append(f"قیمت: {n['price']:,}")
        if n.get('is_peak'):
            parts.append('پیک')
        if n.get('is_holiday'):
            parts.append('تعطیل')
        if n.get('is_weekend'):
            parts.append('آخر هفته')
        parts.append('بسته میزبان' if n.get('is_manual_block') else ('پر' if n.get('is_unavailable') else 'خالی'))
        price = ''
        if eff:
            price = f"<span class='pr{' disc' if n.get('discount') else ''}'>{eff:,}</span>"
            if n.get('discount'):
                price += f"<span class='dsc'>-{n['discount']}٪</span>"
        return (f"<td class='c {cell_class(rec, d)}{extra}' data-r='{rec['room_id']}' data-d='{d.isoformat()}' title='{' · '.join(parts)}'>"
                        f"<span class='dn'>{g2j(d.year, d.month, d.day)[2]}</span>{price}</td>")

    # ---------- سربرگ جدول: ردیف ماه‌ها + ردیف روزها ----------
    def th_extras(d):
        cs = col_extras(d)
        if d.isoformat() in holiday_dates:
            cs.append('holiday')
        if weekday_idx(d) == 6:   # جمعه — آخر هفته ایرانی
            cs.append('friday')
        return (' ' + ' '.join(cs)) if cs else ''

    th_cells = [f"<th class='dayh{th_extras(d)}'>{WD[weekday_idx(d)]}<span class='dnum'>{g2j(d.year, d.month, d.day)[2]}</span></th>" for d in days_flat]
    month_rows = "<tr class='mhrow'><th class='rname' rowspan='2'>اتاق</th>" + "".join(
        f"<th colspan='{len(days)}' class='mh'>{JM[m-1]} {y}</th>" for y, m, days in months
    ) + "</tr>"

    # ---------- ردیف اتاق‌ها ----------
    rows = []
    for rec in rooms:
        meta = rec.get('meta') or {}
        rid = rec['room_id']
        title = meta.get('title') or f"اتاق {rid}"
        village = meta.get('village') or '—'
        host = meta.get('host_name') or '—'
        host_id = meta.get('host_id')
        own = meta.get('own')
        badge = '<span class="me">من</span>' if own else ''
        medal = '' if own else medals.get(rid, '')
        host_link = (f"<a class='hlink' href='https://www.jajiga.com/user/{host_id}' target='_blank'>{host}</a>"
                     if host_id else host)
        cells = "".join(cell_html(rec, d) for d in days_flat)
        rows.append(f"""
<tr class='rrow{" own" if own else ""}'>
  <td class='rname'>{medal}<a class='tlink' href='https://www.jajiga.com/room/{rid}' target='_blank'>{title}</a>{badge}
    <div class='rsub'>{village} · {host_link}</div>
  </td>
  {cells}
  <td class='m occ'><b>{rec['occ'][30]}</b><span class='sub'>٪</span></td>
  <td class='m occ'><b>{rec['occ'][60]}</b><span class='sub'>٪</span></td>
  <td class='m occ'><b>{rec['occ'][90]}</b><span class='sub'>٪</span></td>
  <td class='m num'>{rec['avg_price_90']:,}</td>
  <td class='m num'>{rec['discount_days']}</td>
  <td class='m num'>{rec['peak_days']}</td>
</tr>""")

    legend = """
<div class='legend'>
  <span class='lg'><i class='sw free'></i>خالی</span>
  <span class='lg'><i class='sw booked'></i>پر</span>
  <span class='lg'><i class='sw blocked'></i>بسته میزبان</span>
  <span class='lg'><i class='sw half'></i>نیمه‌پر (روز تعویض)</span>
  <span class='lg'><i class='sw peak'></i>پیک</span>
  <span class='lg'><i class='sw weekend'></i>آخر هفته</span>
  <span class='lg'><i class='sw past'></i>گذشته</span>
  <span class='lg'><i class='sw nodata'></i>بدون داده</span>
</div>"""

    # ---------- تب «گذشته»: هر روزِ سپریشده از اسنپشاتهای روزانه ----------
    # برای هر روز فقط مشاهده «قابل اعتماد» ثبت میشود: روزِ اولِ پنجره هر
    # اسنپشات (دیروز) همیشه is_unavailable است — آرتیفکت API — و نادیده گرفته
    # میشود. پس وضعیتِ روز D از اسنپشاتِ همان روز (وقتی D = «امروز») میآید.
    snap_dir = os.path.join(RADAR_DIR, 'snapshots')
    trusted = {}  # date -> {room_id: night}
    first_observed = {}  # room_id -> اولین روزی که اتاق رصد شده (روز fetch اولین اسنپ‌شات)
    for sf in sorted(os.listdir(snap_dir)):
        if not sf.endswith('.json'):
            continue
        try:
            snap = json.load(open(os.path.join(snap_dir, sf), encoding='utf-8'))
        except Exception:
            continue
        # «دیروزِ واقعیِ» زمان fetch — آرتیفکت API (همیشه پر) و باید نادیده گرفته شود
        fa = str(snap.get('fetched_at') or '')
        try:
            snap_date = date.fromisoformat(fa[:10])
        except Exception:
            snap_date = today
        artifact_yesterday = (snap_date - timedelta(days=1)).isoformat()
        for rid, rdata in (snap.get('rooms') or {}).items():
            if str(rid) not in first_observed:
                first_observed[str(rid)] = snap_date.isoformat()
            nights = rdata.get('nights') or []
            for n in nights:
                nd = n['date']
                # فقط روزهای سپری‌شده (قبل از امروز، نه آرتیفکتِ دیروزِ fetch) —
                # تب «دیتابیس» فقط گذشته است؛ امروز در تب تقویم دیده می‌شود
                if nd < today.isoformat() and nd != artifact_yesterday:
                    # آخرین اسنپ‌شات (مرتب‌شده) برنده است — وضعیت نهاییِ روز
                    trusted.setdefault(nd, {})[str(rid)] = n
    past_days = sorted(trusted.keys())

    # گروهبندی ماه شمسی برای سربرگ گذشته
    past_months = []
    for dstr in past_days:
        y, m, _ = g2j(*map(int, dstr.split('-')))
        if not past_months or past_months[-1][0] != y or past_months[-1][1] != m:
            past_months.append([y, m, [dstr]])
        else:
            past_months[-1][2].append(dstr)
    past_mh_rows = ("<tr class='mhrow'><th class='rname' rowspan='2'>اتاق</th>" + "".join(
        f"<th colspan='{len(ds)}' class='mh'>{JM[m-1]} {y}</th>" for y, m, ds in past_months
    ) + "</tr>") if past_months else ""

    def past_th_for(dstr):
        y, m, dd = map(int, dstr.split('-'))
        dt = date(y, m, dd)
        _, _, jd = g2j(y, m, dd)
        cs = ['wb'] if weekday_idx(dt) == 0 else []
        if dstr == today.isoformat():
            cs.append('today')
        return f"<th class='dayh{' ' + ' '.join(cs) if cs else ''}'>{WD[weekday_idx(dt)]}<span class='dnum'>{jd}</span></th>"

    past_th = [past_th_for(dstr) for dstr in past_days]

    def past_status_of(rid, dstr):
        """کلاس وضعیت سلول گذشته: booked/free از اسنپ‌شات همان روز،
        half اگه دیتای مستقیم نباشد و دیروزش پر باشد،
        notracked اگه اتاق از بعدِ آن روز شروع به رصد شده، وگرنه nodata."""
        n = trusted.get(dstr, {}).get(str(rid))
        if n is not None:
            if n.get('is_manual_block'):
                return 'blocked', n
            return ('booked' if n.get('is_unavailable') else 'free'), n
        fo = first_observed.get(str(rid))
        if fo and fo > dstr:
            return 'notracked', None
        dt = date(*map(int, dstr.split('-')))
        prev_d = (dt - timedelta(days=1)).isoformat()
        prev = None
        for sf in sorted(os.listdir(snap_dir)):
            if not sf.endswith('.json'):
                continue
            try:
                s = json.load(open(os.path.join(snap_dir, sf), encoding='utf-8'))
            except Exception:
                continue
            if str(rid) in (s.get('rooms') or {}) and (s['rooms'][str(rid)].get('nights') or []):
                pn = next((x for x in s['rooms'][str(rid)]['nights'] if x['date'] == prev_d), None)
                if pn is not None:
                    prev = pn
                    break
        if prev and prev.get('is_unavailable'):
            return 'half', None
        return 'nodata', None

    def past_cell(rid, dstr):
        cls, n = past_status_of(rid, dstr)
        _, _, jd = g2j(*map(int, dstr.split('-')))
        dt = date(*map(int, dstr.split('-')))
        cs = ['wb'] if weekday_idx(dt) == 0 else []
        extra = (' ' + ' '.join(cs)) if cs else ''
        if cls in ('nodata', 'notracked'):
            fo = first_observed.get(str(rid))
            parts = [jalali_str(dstr),
                     f'از {jalali_str(fo)} رصد می‌شود' if fo else 'بدون داده']
        elif cls == 'half':
            parts = [jalali_str(dstr), 'نیمه‌پر (دیروز پر بود)']
        elif cls == 'blocked':
            parts = [jalali_str(dstr), 'بسته میزبان']
        else:
            parts = [jalali_str(dstr), 'پر' if cls == 'booked' else 'خالی']
        eff = eff_price(n.get('price'), n.get('discount')) if n else None
        if eff:
            parts.append(f"قیمت: {eff:,}")
        price = f"<span class='pr{' disc' if n and n.get('discount') else ''}'>{eff:,}</span>" if eff else ''
        return (f"<td class='c {cls}{extra}' data-r='{rid}' data-d='{dstr}' title='{' · '.join(parts)}'>"
                        f"<span class='dn'>{jd}</span>{price}</td>")

    past_rows = []
    for rec in rooms:
        meta = rec.get('meta') or {}
        rid = rec['room_id']
        title = meta.get('title') or f'اتاق {rid}'
        village = meta.get('village') or '—'
        host = meta.get('host_name') or '—'
        host_id = meta.get('host_id')
        own = meta.get('own')
        badge = '<span class="me">من</span>' if own else ''
        host_link = (f"<a class='hlink' href='https://www.jajiga.com/user/{host_id}' target='_blank'>{host}</a>"
                     if host_id else host)
        cells = ''.join(past_cell(rid, dstr) for dstr in past_days)
        past_rows.append(f"""
<tr class='rrow{' own' if own else ''}'>
  <td class='rname'><a class='tlink' href='https://www.jajiga.com/room/{rid}' target='_blank'>{title}</a>{badge}
    <div class='rsub'>{village} · {host_link}</div>
  </td>
  {cells}
</tr>""")

    # آمار خلاصه تب دیتابیس
    past_stats = {'booked': 0, 'free': 0, 'half': 0, 'blocked': 0, 'nodata': 0, 'notracked': 0}
    for dstr in past_days:
        for rec in rooms:
            cls, _ = past_status_of(rec['room_id'], dstr)
            past_stats[cls] += 1

    # پیلود اکسل تب دیتابیس (گذشته)
    past_payload = {"today": today.isoformat(), "dates": [], "rooms": []}
    for dstr in past_days:
        dt_p = date(*map(int, dstr.split('-')))
        past_payload["dates"].append({
            "g": dstr,
            "j": jalali_str(dstr),
            "wd": WD[weekday_idx(dt_p)],
        })
    for rec in rooms:
        meta = rec.get('meta') or {}
        cells = {}
        for dstr in past_days:
            cls, n = past_status_of(rec['room_id'], dstr)
            st = {'booked': 'پر', 'free': 'خالی', 'half': 'نیمه‌پر', 'blocked': 'بسته میزبان',
                  'nodata': 'بدون داده', 'notracked': 'از بعد رصد'}.get(cls, cls)
            parts = [st]
            if cls in ('nodata', 'notracked'):
                fo = first_observed.get(str(rec['room_id']))
                if fo:
                    parts = [f'از {jalali_str(fo)} رصد می‌شود']
            eff = eff_price(n.get('price'), n.get('discount')) if n else None
            if eff:
                m = eff / 1_000_000
                mstr = f"{m:.1f}".rstrip('0').rstrip('.')
                parts.append(f"{mstr}M")
            cells[dstr] = {"t": " · ".join(parts), "s": cls}
        past_payload["rooms"].append({
            "id": rec['room_id'],
            "label": meta.get('title') or f"اتاق {rec['room_id']}",
            "village": meta.get('village') or '—',
            "own": bool(meta.get('own')),
            "cells": cells,
        })
    past_data_json = json.dumps(past_payload, ensure_ascii=False)

    if past_days:
        past_table = f"""<table class='cal'>
<thead>
{past_mh_rows}
<tr class='dayrow'>{''.join(past_th)}</tr>
</thead>
<tbody>
{''.join(past_rows)}
</tbody>
</table>"""
    else:
        past_table = "<div class='empty'>هنوز روزی ثبت نشده است — از فردا هر روز یک ستون اضافه میشود.</div>"

    legend_past = """
<div class='legend'>
  <span class='lg'><i class='sw free'></i>خالی</span>
  <span class='lg'><i class='sw booked'></i>پر</span>
  <span class='lg'><i class='sw blocked'></i>بسته میزبان</span>
  <span class='lg'><i class='sw half'></i>نیمه‌پر (دیروزش پر بود)</span>
  <span class='lg'><i class='sw notracked'></i>از بعد رصد</span>
  <span class='lg'><i class='sw nodata'></i>بدون داده</span>
  <span class='note'>هر روز که می‌گذرد یک ستون به این جدول اضافه می‌شود · وضعیت هر روز از اسنپ‌شات همان روز ثبت شده است</span>
</div>"""

    # ---------- پیلود JSON برای دکمه خروجی اکسل ----------
    def cell_export(rec, d):
        n = rec['by_date'].get(d.isoformat())
        if n is None:
            return {"t": "بدون داده", "s": "nodata"}
        cls = cell_class(rec, d)
        st = {"past": "گذشته", "booked": "پر", "blocked": "بسته میزبان", "half": "نیمه‌پر", "peak": "پیک",
              "weekend": "آخر هفته", "free": "خالی"}.get(cls, cls)
        parts = [st]
        eff = eff_price(n.get('price'), n.get('discount'))
        if eff:
            m = eff / 1_000_000
            mstr = f"{m:.1f}".rstrip('0').rstrip('.')
            parts.append(f"{mstr}M")
        if n.get('discount'):
            parts.append(f"-{n['discount']}%")
        return {"t": " · ".join(parts), "s": cls}

    payload = {"today": today.isoformat(), "dates": [], "rooms": []}
    for d in days_flat:
        jy2, jm2, jd2 = g2j(d.year, d.month, d.day)
        payload["dates"].append({
            "g": d.isoformat(),
            "j": f"{jd2} {JM[jm2 - 1]}",
            "wd": WD[weekday_idx(d)],
            "holiday": d.isoformat() in holiday_dates,
        })
    for rec in rooms:
        meta = rec.get('meta') or {}
        payload["rooms"].append({
            "id": rec['room_id'],
            "label": meta.get('title') or f"اتاق {rec['room_id']}",
            "village": meta.get('village') or '—',
            "own": bool(meta.get('own')),
            "occ30": rec['occ'][30], "occ60": rec['occ'][60], "occ90": rec['occ'][90],
            "avg": rec['avg_price_90'] or '',
            "discount": rec['discount_days'], "peak": rec['peak_days'],
            "cells": {d.isoformat(): cell_export(rec, d) for d in days_flat},
        })
    data_json = json.dumps(payload, ensure_ascii=False)

    export_js = r"""
<script type='application/json' id='radarData'>{DATA_JSON}</script>
<script>
(function(){
  var btn = document.getElementById('exportBtn');
  if (!btn) return;
  btn.addEventListener('click', function(){
    var D = JSON.parse(document.getElementById('radarData').textContent);
    if (typeof XLSX === 'undefined'){ alert('کتابخانه اکسل (SheetJS) بارگذاری نشد — اینترنت را بررسی کنید.'); return; }
    var STATUS = {
      'past':    {fill:'475569', font:'ffffff'},
      'booked':  {fill:'dc2626', font:'ffffff'},
      'blocked': {fill:'9a7b4f', font:'ffffff'},
      'half':    {fill:'ea580c', font:'ffffff'},
      'peak':    {fill:'7c3aed', font:'ffffff'},
      'weekend': {fill:'0369a1', font:'ffffff'},
      'free':    {fill:'16a34a', font:'ffffff'},
      'nodata':  {fill:'1e293b', font:'64748b'}
    };
    function cellStyle(c){
      var s = STATUS[c.s] || STATUS.nodata;
      return { fill: { fgColor: { rgb: s.fill } }, font: { color: { rgb: s.font } }, alignment: { horizontal: 'center', vertical: 'center' } };
    }
    var aoa = [['اتاق','روستا','میزبان']];
    D.dates.forEach(function(d){ aoa[0].push(d.wd + ' ' + d.j); });
    aoa[0] = aoa[0].concat(['۳۰ روز','۶۰ روز','۹۰ روز','میانگین شب','تخفیف','پیک']);
    var styled = [];
    D.rooms.forEach(function(r, ri){
      var row = [r.label, r.village, ''];
      D.dates.forEach(function(d, di){
        var c = r.cells[d.g] || {t:'', s:'nodata'};
        row.push(c.t);
        styled.push({r: ri + 1, c: di + 3, s: c.s});
      });
      row = row.concat([r.occ30 + '%', r.occ60 + '%', r.occ90 + '%', r.avg, r.discount, r.peak]);
      aoa.push(row);
    });
    var ws = XLSX.utils.aoa_to_sheet(aoa);
    var wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'تقویم');
    ws['!cols'] = [{wch:34},{wch:11},{wch:16}];
    D.dates.forEach(function(){ ws['!cols'].push({wch:11}); });
    [].push.apply(ws['!cols'], [{wch:9},{wch:9},{wch:9},{wch:12},{wch:9},{wch:9}]);
    var key;
    for (var i = 0; i < styled.length; i++){
      key = XLSX.utils.encode_cell({r: styled[i].r, c: styled[i].c});
      if (ws[key]) ws[key].s = cellStyle(styled[i]);
    }
    for (var k in ws){
      if (k !== 'A1' && k !== 'B1' && k !== 'C1') continue;
      var cell = ws[k];
      if (!cell) continue;
      cell.s = { fill:{ fgColor:{ rgb:'1e3a5f' } }, font:{ bold:true, color:{ rgb:'ffffff' } }, alignment:{ horizontal:'center', vertical:'center' } };
    }
    XLSX.writeFile(wb, 'radar-' + D.today + '.xlsx');
  });
})();
</script>"""
    export_js = export_js.replace('{DATA_JSON}', data_json)

    past_export_js = r"""
<script type='application/json' id='radarPastData'>{PAST_DATA_JSON}</script>
<script>
(function(){
  var btn = document.getElementById('exportPastBtn');
  if (!btn) return;
  btn.addEventListener('click', function(){
    var D = JSON.parse(document.getElementById('radarPastData').textContent);
    if (typeof XLSX === 'undefined'){ alert('کتابخانه اکسل (SheetJS) بارگذاری نشد — اینترنت را بررسی کنید.'); return; }
    var STATUS = {
      'past':    {fill:'475569', font:'ffffff'},
      'booked':  {fill:'dc2626', font:'ffffff'},
      'blocked': {fill:'9a7b4f', font:'ffffff'},
      'half':    {fill:'ea580c', font:'ffffff'},
      'peak':    {fill:'7c3aed', font:'ffffff'},
      'weekend': {fill:'0369a1', font:'ffffff'},
      'free':    {fill:'16a34a', font:'ffffff'},
      'nodata':  {fill:'1e293b', font:'64748b'}
    };
    function cellStyle(c){
      var s = STATUS[c.s] || STATUS.nodata;
      return { fill: { fgColor: { rgb: s.fill } }, font: { color: { rgb: s.font } }, alignment: { horizontal: 'center', vertical: 'center' } };
    }
    var aoa = [['اتاق','روستا','میزبان']];
    D.dates.forEach(function(d){ aoa[0].push(d.j); });
    var styled = [];
    D.rooms.forEach(function(r, ri){
      var row = [r.label, r.village, ''];
      D.dates.forEach(function(d, di){
        var c = r.cells[d.g] || {t:'', s:'nodata'};
        row.push(c.t);
        styled.push({r: ri + 1, c: di + 3, s: c.s});
      });
      aoa.push(row);
    });
    var ws = XLSX.utils.aoa_to_sheet(aoa);
    var wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'دیتابیس');
    ws['!cols'] = [{wch:34},{wch:11},{wch:16}];
    D.dates.forEach(function(){ ws['!cols'].push({wch:11}); });
    var key;
    for (var i = 0; i < styled.length; i++){
      key = XLSX.utils.encode_cell({r: styled[i].r, c: styled[i].c});
      if (ws[key]) ws[key].s = cellStyle(styled[i]);
    }
    for (var k in ws){
      if (k !== 'A1' && k !== 'B1' && k !== 'C1') continue;
      var cell = ws[k];
      if (!cell) continue;
      cell.s = { fill:{ fgColor:{ rgb:'1e3a5f' } }, font:{ bold:true, color:{ rgb:'ffffff' } }, alignment:{ horizontal:'center', vertical:'center' } };
    }
    XLSX.writeFile(wb, 'radar-db-' + D.today + '.xlsx');
  });
})();
</script>"""
    past_export_js = past_export_js.replace('{PAST_DATA_JSON}', past_data_json)

    rev_js = r"""
<script type='application/json' id='revRooms'>{REV_ROOMS_JSON}</script>
<script type='application/json' id='revEnds'>{REV_ENDS_JSON}</script>
<script>
(function(){
  var ROOMS = JSON.parse(document.getElementById('revRooms').textContent);
  var META = JSON.parse(document.getElementById('revEnds').textContent);
  var COMM = 0.12;
  var revSortKey = null, revSortDir = -1;
  var tbody = document.getElementById('revHostTbody');
  var curFrom = null, curTo = null;

  function fmt(n){ return (n||0).toLocaleString('en-US'); }

  // برچسب شمسی یک تاریخ میلادی
  function jlabel(g){
    var r = '';
    META.months.forEach(function(mo){
      mo.days.forEach(function(d){ if (d.g === g) r = d.jd + ' ' + mo.name; });
    });
    return r;
  }

  // جمع‌بندی مجدد برای دوره انتخابی — بدون نیاز به refetch
  function computeHosts(startStr, endStr){
    var start = new Date(startStr + 'T00:00:00');
    var end = new Date(endStr + 'T00:00:00');
    var rooms = ROOMS.map(function(r){
      var nMap = {};
      for (var i = 0; i < r.nights.length; i++) nMap[r.nights[i].d] = r.nights[i];
      var booked = 0, gross = 0, disc = 0;
      var cur = new Date(start.getTime());
      while (cur <= end){
        var ds = cur.toISOString().slice(0, 10);
        var n = nMap[ds];
        var e = window.RE ? window.RE.get(r.id, ds) : null;
        var isBooked, price;
        if (e){
          if (e.s === 'free' || e.s === 'blocked'){ isBooked = false; price = 0; }
          else if (e.s === 'booked'){ isBooked = true; price = (e.p != null) ? e.p : (n ? n.p : 0); }
          else { isBooked = !!n; price = (e.p != null) ? e.p : (n ? n.p : 0); }
        } else {
          isBooked = !!n; price = n ? n.p : 0;
        }
        if (isBooked){ booked++; gross += price; if (n) disc += Math.max(0, n.b - price); }
        cur.setDate(cur.getDate() + 1);
      }
      var commission = Math.round(gross * COMM);
      return { id: r.id, title: r.title, host_name: r.host_name, host_id: r.host_id,
               booked: booked, gross: gross, discount: disc, commission: commission, net: gross - commission };
    });
    rooms.sort(function(a,b){ return b.net - a.net; });
    var horder = [], hmap = {};
    rooms.forEach(function(r){
      var key = r.host_id || r.host_name;
      if (!hmap[key]){ hmap[key] = { host_name:r.host_name, host_id:r.host_id, rooms_count:0, booked:0, gross:0, discount:0, commission:0, net:0, _rooms:[] }; horder.push(key); }
      var h = hmap[key];
      h.rooms_count++; h.booked += r.booked; h.gross += r.gross; h.discount += r.discount; h.commission += r.commission; h.net += r.net;
      h._rooms.push(r);
    });
    var hosts = horder.map(function(k){ return hmap[k]; });
    hosts.forEach(function(h){
      h.rooms_html = h._rooms.map(function(r){
        return "<div class='nrow'><a class='tlink' href='https://www.jajiga.com/room/" + r.id + "' target='_blank'>" + r.title + "</a> " +
          "<span class='en' style='color:#64748b;font-size:11px'>(" + r.id + ")</span> " +
          "<span class='en' style='color:#64748b;font-size:11px'>" + r.booked + " شب</span> " +
          "<span class='np'>" + fmt(r.gross) + "</span> " +
          "<span class='nnet'>" + fmt(r.net) + "</span></div>";
      }).join('');
      delete h._rooms;
    });
    hosts.sort(function(a,b){ return b.net - a.net; });
    var tot = { net: 0, booked: 0 };
    hosts.forEach(function(h,i){
      h.rank = i + 1;
      h.medal = h.rank === 1 ? '🥇' : h.rank === 2 ? '🥈' : h.rank === 3 ? '🥉' : '';
      tot.net += h.net; tot.booked += h.booked;
    });
    return { hosts: hosts, tot: tot };
  }

  function sv(h){
    switch(revSortKey){
      case 'rank': return h.net;
      case 'rooms': return h.rooms_count;
      case 'booked': return h.booked;
      case 'gross': return h.gross;
      case 'discount': return h.discount;
      case 'commission': return h.commission;
      case 'net': return h.net;
      case 'host': return h.host_name;
      default: return 0;
    }
  }

  function render(){
    var cur = computeHosts(curFrom, curTo);
    var arr = cur.hosts.slice();
    if (revSortKey){
      arr.sort(function(a,b){
        var av = sv(a), bv = sv(b);
        if (av === bv) return b.net - a.net;
        if (typeof av === 'string') return revSortDir * av.localeCompare(bv, 'fa');
        return revSortDir * (av - bv);
      });
    }
    tbody.innerHTML = arr.map(function(h,i){
      var rank = i + 1;
      var medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : '';
      var hostCell = h.host_id
        ? '<a class="hlink" href="https://www.jajiga.com/user/' + h.host_id + '" target="_blank" rel="noopener">' + h.host_name + '</a>'
        : '<span style="color:#64748b">' + h.host_name + '</span>';
      return '<tr class="hrev-row rank-' + rank + '" data-i="' + i + '">' +
        '<td><span class="medal">' + medal + '</span> <span class="rank-num en">' + rank + '</span></td>' +
        '<td class="hc">' + hostCell + '</td>' +
        '<td><span class="en">' + h.rooms_count + '</span></td>' +
        '<td><span class="en">' + h.booked + '</span></td>' +
        '<td><span class="en">' + fmt(h.gross) + '</span></td>' +
        '<td>' + (h.discount ? '<span class="en" style="color:#f87171">' + fmt(h.discount) + '</span>' : '<span class="en" style="color:#64748b">0</span>') + '</td>' +
        '<td><span class="en" style="color:#f87171">' + fmt(h.commission) + '</span></td>' +
        '<td><span class="en" style="color:#34d399;font-weight:800">' + fmt(h.net) + '</span></td>' +
        '<td><span class="chev" id="hchev-' + i + '">▾</span></td>' +
      '</tr>' +
      '<tr class="hrev-detail" id="hdet-' + i + '" style="display:none">' +
        '<td colspan="9"><b>اقامتگاه‌های این میزبان (ناخالص / خالص):</b> ' + (h.rooms_html || '<span class="empty">—</span>') + '</td>' +
      '</tr>';
    }).join('');
    var rows = tbody.querySelectorAll('.hrev-row');
    Array.prototype.forEach.call(rows, function(tr){
      tr.onclick = function(e){
        if (e.target.closest('a')) return;
        var i = tr.dataset.i;
        var det = document.getElementById('hdet-' + i);
        var chev = document.getElementById('hchev-' + i);
        var show = det.style.display === 'none';
        det.style.display = show ? '' : 'none';
        chev.textContent = show ? '▴' : '▾';
      };
    });
    var rs = document.querySelector('.rev-title .rsub');
    if (rs) rs.textContent = 'شب‌های پرِ آینده (از ' + jlabel(curFrom) + ' تا ' + jlabel(curTo) + ') · کمیسیون ۱۲٪ · مجموع خالص: ' + fmt(cur.tot.net) + ' تومان';
  }

  document.querySelectorAll('th[data-revkey]').forEach(function(th){
    th.onclick = function(){
      var k = th.dataset.revkey;
      if (revSortKey !== k){ revSortKey = k; revSortDir = -1; }
      else if (revSortDir === -1){ revSortDir = 1; }
      else { revSortKey = null; revSortDir = -1; }
      document.querySelectorAll('th .arrow').forEach(function(a){ a.textContent = ''; });
      if (revSortKey){ var a = th.querySelector('.arrow'); a.textContent = revSortDir === -1 ? '▼' : '▲'; }
      render();
    };
  });

  // ---------- تقویم شمسی «از / تا» ----------
  var chips = document.querySelectorAll('.rc-chip');
  var fromField = document.getElementById('revFromField');
  var toField = document.getElementById('revToField');
  var fromVal = document.getElementById('revFromVal');
  var toVal = document.getElementById('revToVal');
  var JWD = ['ش','ی','د','س','چ','پ','ج'];
  var pop = null, popWhich = null, popMon = 0;

  function resetSort(){
    revSortKey = null; revSortDir = -1;
    document.querySelectorAll('th .arrow').forEach(function(a){ a.textContent = ''; });
  }
  function setLabels(){
    fromVal.textContent = jlabel(curFrom) || '—';
    toVal.textContent = jlabel(curTo) || '—';
  }
  function applyRange(){
    if (curFrom && curTo && curFrom > curTo){
      var t = curFrom; curFrom = curTo; curTo = t;
    }
    setLabels();
    chips.forEach(function(c){ c.classList.remove('active'); });
    resetSort();
    render();
  }

  // پاپ‌آپ تقویم
  function monthIndexOf(g){
    for (var i = 0; i < META.months.length; i++){
      var hit = false;
      META.months[i].days.forEach(function(d){ if (d.g === g) hit = true; });
      if (hit) return i;
    }
    return 0;
  }
  function renderPopup(){
    var mo = META.months[popMon];
    pop.querySelector('.cal-pop-title').textContent = mo.name + ' ' + mo.y;
    var grid = pop.querySelector('.cal-pop-grid');
    grid.innerHTML = JWD.map(function(w){ return "<span class='cal-pop-wd'>" + w + "</span>"; }).join('');
    var lead = mo.days[0].wd;
    for (var i = 0; i < lead; i++) grid.innerHTML += "<span></span>";
    var lo = (curFrom && curTo) ? (curFrom < curTo ? curFrom : curTo) : null;
    var hi = (curFrom && curTo) ? (curFrom < curTo ? curTo : curFrom) : null;
    var on = popWhich === 'from' ? curFrom : curTo;
    mo.days.forEach(function(d){
      var dis = d.g < META.min || d.g > META.max;
      var cls = 'cal-pop-day';
      if (!dis && d.g === on) cls += ' sel';
      else if (!dis && lo && hi && d.g >= lo && d.g <= hi) cls += ' inrange';
      if (d.wd === 6) cls += ' fri';
      grid.innerHTML += "<button class='" + cls + "' data-g='" + d.g + "'" + (dis ? ' disabled' : '') + ">" + d.jd + "</button>";
    });
    pop.querySelectorAll('.cal-pop-day').forEach(function(b){
      b.onclick = function(){
        if (b.disabled) return;
        var g = b.getAttribute('data-g');
        if (popWhich === 'from') curFrom = g; else curTo = g;
        closePopup();
        applyRange();
      };
    });
    pop.querySelectorAll('.cal-pop-nav').forEach(function(b){
      b.onclick = function(){
        var nm = popMon + (+b.getAttribute('data-nav'));
        if (nm < 0 || nm >= META.months.length) return;
        popMon = nm;
        renderPopup();
      };
    });
  }
  function openPopup(which, field){
    // کلیک دوباره روی همان فیلد → بستن
    if (pop && popWhich === which) {
      closePopup();
      return;
    }
    popWhich = which;
    popMon = monthIndexOf(which === 'from' ? curFrom : curTo);
    if (pop) pop.remove();
    pop = document.createElement('div');
    pop.className = 'cal-pop';
    pop.innerHTML =
      "<div class='cal-pop-head'>" +
        "<button class='cal-pop-nav' data-nav='-1'>‹</button>" +
        "<span class='cal-pop-title'></span>" +
        "<button class='cal-pop-nav' data-nav='1'>›</button>" +
      "</div><div class='cal-pop-grid'></div>";
    renderPopup();
    document.body.appendChild(pop);
    var r = field.getBoundingClientRect();
    var vw = window.innerWidth || document.documentElement.clientWidth;
    var left = r.left, top = r.bottom + 6;
    if (left + 264 > vw - 8) left = Math.max(8, vw - 264 - 8);
    pop.style.left = left + 'px';
    pop.style.top = top + 'px';
    fromField.classList.remove('open'); toField.classList.remove('open');
    field.classList.add('open');
  }
  function closePopup(){
    if (!pop) return;
    pop.remove(); pop = null;
    fromField.classList.remove('open'); toField.classList.remove('open');
  }

  fromField.onclick = function(){ openPopup('from', fromField); };
  toField.onclick = function(){ openPopup('to', toField); };
  document.addEventListener('click', function(e){
    if (!pop) return;
    if (!fromField.contains(e.target) && !toField.contains(e.target) && !pop.contains(e.target))
      closePopup();
  });

  chips.forEach(function(ch){
    ch.onclick = function(){
      chips.forEach(function(c){ c.classList.remove('active'); });
      ch.classList.add('active');
      curFrom = ch.getAttribute('data-start');
      curTo = ch.getAttribute('data-end');
      applyRange();
    };
  });
  curFrom = META.default_start || META.min;
  curTo = META.default_end || META.max;
  setLabels();
  render();
  window.__revRender = function(){ applyRange(); };
})();
</script>
""".replace('{REV_ROOMS_JSON}', rev_rooms_json).replace('{REV_ENDS_JSON}', rev_ends_json)

    edit_js = ('<script>\n'
               + open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'radar_edit_module.js'), encoding='utf-8').read()
               + '\n</script>')

    horizon_day = days_flat[-1] if days_flat else today + timedelta(days=44)
    hor_y, hor_m, hor_d = g2j(horizon_day.year, horizon_day.month, horizon_day.day)
    html = f"""<!DOCTYPE html>
<html lang='fa' dir='rtl'>
<head>
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>رادار رقبا — جاجیگا</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📡</text></svg>">
<link href='https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;700&display=swap' rel='stylesheet'>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Vazirmatn',Tahoma,sans-serif; background:#0b1526; color:#e2e8f0; }}
.wrap {{ max-width:1600px; margin:0 auto; padding:18px; }}
header {{ background:linear-gradient(135deg,#0f2a43,#0b1526 60%); border:1px solid #1e3a5f; border-radius:14px; padding:18px 22px; margin-bottom:16px; }}
h1 {{ font-size:22px; font-weight:700; color:#f1f5f9; }}
h1 .radar {{ color:#38bdf8; }}
.sub {{ color:#94a3b8; font-size:12px; margin-top:6px; }}
.legend {{ display:flex; gap:14px; flex-wrap:wrap; background:#111f35; border:1px solid #1e3a5f; border-radius:10px; padding:10px 14px; margin-bottom:14px; }}
.lg {{ display:flex; align-items:center; gap:6px; font-size:12px; color:#cbd5e1; }}
.sw {{ width:14px; height:14px; border-radius:4px; display:inline-block; }}
.free {{ background:#1a4d7a; }}
.booked {{ background:#6b2b2b; }}
.blocked {{ background:repeating-linear-gradient(45deg,#5b3a1e 0 6px,#4a2f18 6px 12px); }}
.half {{ background:#7b5a1e; }}
.peak {{ background:#4a3b6b; }}
.weekend {{ background:#155e63; }}
.past {{ background:#16202f; }}
.nodata {{ background:#0f172a; border:1px dashed #334155; }}
.table-wrap {{ overflow-x:auto; border:1px solid #1e3a5f; border-radius:12px; background:#0d1a2e; max-height:78vh; overflow-y:auto; scrollbar-width:thin; scrollbar-color:#475569 #0b1526; scrollbar-gutter:stable; }}
.table-wrap::-webkit-scrollbar {{ width:10px; height:10px; }}
.table-wrap::-webkit-scrollbar-track {{ background:#0b1526; border-radius:8px; }}
.table-wrap::-webkit-scrollbar-thumb {{ background:linear-gradient(180deg,#475569,#334155); border-radius:8px; border:2px solid #0b1526; }}
.table-wrap::-webkit-scrollbar-thumb:hover {{ background:linear-gradient(180deg,#5b6f8f,#475569); }}
.table-wrap::-webkit-scrollbar-corner {{ background:#0b1526; }}
@media (pointer:fine) {{ .table-wrap {{ scrollbar-width:thin; scrollbar-color:#475569 #0b1526; }} }}
table.cal {{ border-collapse:collapse; width:100%; font-size:11px; --mhrow-h:36px; }}
.cal th, .cal td {{ border:1px solid #1e3a5f; padding:4px 3px; text-align:center; }}
.cal thead th {{ background:#132a47; color:#7dd3fc; font-weight:500; position:sticky; top:0; z-index:4; }}
.cal thead tr.mhrow th {{ top:0; height:var(--mhrow-h); box-sizing:border-box; }}
.cal thead tr.dayrow th {{ top:var(--mhrow-h); }}
.cal th.rname {{ position:sticky; right:0; background:#132a47; z-index:6; min-width:230px; text-align:right; padding:8px 10px; }}
.cal tr.mhrow th.rname {{ top:0; vertical-align:middle; }}
.cal td.rname {{ position:sticky; right:0; background:#0f1f36; z-index:2; min-width:230px; text-align:right; padding:8px 10px; }}
.cal tr.own td.rname {{ background:#0c2b24; }}
.cal th.mh {{ background:#1b3a5f; color:#f8fafc; font-size:13px; padding:7px; }}
.cal th.dayh {{ background:#0e2a47; color:#64748b; font-weight:400; padding:4px 2px; line-height:1.5; }}
.cal th.dayh .dnum {{ display:block; color:#7dd3fc; font-size:11px; font-weight:700; }}
.cal td.c {{ min-width:34px; height:34px; padding:2px; }}
.cal td.c .dn {{ display:block; font-size:9px; color:rgba(255,255,255,.55); }}
.cal td.c .pr {{ display:block; font-size:8px; color:#cbd5e1; direction:ltr; }}
.cal td.c .pr.disc {{ color:#fbbf24; }}
.cal td.c .dsc {{ display:block; font-size:8px; color:#fbbf24; font-weight:700; }}
.cal td.c.past {{ background:#1e293b; }}
.cal td.c.past .dn {{ color:#475569; }}
.cal td.c.nodata {{ background:#0f172a; border:1px dashed #334155; }}
.cal td.c.nodata .dn {{ color:#334155; }}
.cal td.c.notracked {{ background:#152238; }}
.cal td.c.notracked .dn {{ color:#3b5b7a; }}
.cal td.c.free {{ background:#1a4d7a; }}
.cal td.c.booked {{ background:#6b2b2b; }}
.cal td.c.blocked {{ background:repeating-linear-gradient(45deg,#5b3a1e 0 6px,#4a2f18 6px 12px); }}
.cal td.c.half {{ background:#7b5a1e; }}
.cal td.c.peak {{ background:#4a3b6b; }}
.cal td.c.weekend {{ background:#155e63; }}
.cal td.c.wb {{ border-right:2px solid #4a729c; background-image:linear-gradient(270deg, rgba(74,114,156,.16), rgba(74,114,156,0) 70%); }}
.cal td.c.mb {{ border-right:3px solid #3f7cc4; }}
.cal th.dayh.wb {{ border-right:2px solid #4a729c; }}
.cal th.dayh.today {{ background:#1e3a5f; }}
.cal th.dayh.today .dnum {{ color:#fbbf24; }}
.cal th.dayh.mb {{ border-right:3px solid #3f7cc4; }}
.cal th.dayh.holiday .dnum {{ color:#f87171; }}
.cal th.dayh.friday .dnum {{ color:#f87171; }}
.cal td.c:hover {{ outline:2px solid rgba(255,255,255,.35); cursor:default; }}
td.m {{ min-width:52px; font-size:12px; }}
td.m.occ b {{ color:#38bdf8; font-size:14px; }}
td.m.num {{ color:#e2e8f0; direction:ltr; font-family:Consolas,monospace; }}
td.m .sub {{ font-size:9px; color:#64748b; }}
.tlink {{ color:#38bdf8; text-decoration:none; font-size:12.5px; font-weight:500; }}
.tlink:hover {{ text-decoration:underline; }}
.hlink {{ color:#fb923c; text-decoration:none; font-size:11px; }}
.rsub {{ color:#64748b; font-size:10.5px; margin-top:3px; }}
.me {{ display:inline-block; background:#0d9488; color:#fff; border-radius:6px; font-size:9.5px; padding:1px 6px; margin-right:6px; vertical-align:middle; }}
.hrow {{ display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap; }}
.hd-actions {{ display:flex; gap:8px; flex-wrap:wrap; }}
.export-btn {{ background:linear-gradient(135deg,#0d9488,#0f766e); color:#fff; border:none; border-radius:10px; padding:10px 18px; font-family:inherit; font-size:13px; font-weight:600; cursor:pointer; box-shadow:0 4px 14px rgba(13,148,136,.35); transition:transform .15s, box-shadow .15s; }}
.export-btn:hover {{ transform:translateY(-1px); box-shadow:0 6px 18px rgba(13,148,136,.5); }}
.export-btn.past-btn {{ background:linear-gradient(135deg,#4a3b6b,#372a52); box-shadow:0 4px 14px rgba(74,59,107,.35); }}
.export-btn.past-btn:hover {{ box-shadow:0 6px 18px rgba(74,59,107,.5); }}
.stats {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:14px; }}
.stat {{ flex:1; min-width:110px; background:#111f35; border:1px solid #1e3a5f; border-radius:12px; padding:12px 14px; text-align:center; }}
.stat b {{ display:block; font-size:22px; color:#38bdf8; font-weight:700; }}
.stat span {{ font-size:11.5px; color:#94a3b8; }}
.tabs {{ display:flex; gap:8px; margin-bottom:14px; }}
.tab-btn {{ background:#111f35; color:#94a3b8; border:1px solid #1e3a5f; border-radius:10px; padding:9px 26px; font-family:inherit; font-size:13px; font-weight:600; cursor:pointer; transition:all .15s; }}
.tab-btn:hover {{ color:#e2e8f0; border-color:#2d4668; }}
.tab-btn.active {{ background:linear-gradient(135deg,#0d9488,#0f766e); color:#fff; border-color:#0f766e; box-shadow:0 3px 12px rgba(13,148,136,.3); }}
.tab-pane {{ display:none; }}
.tab-pane.active {{ display:block; }}
.legend .note {{ color:#64748b; font-size:11px; margin-right:auto; }}
.empty {{ color:#94a3b8; font-size:13px; text-align:center; padding:30px; border:1px dashed #1e3a5f; border-radius:12px; background:#0d1a2e; }}
.rev-title {{ font-size:16px; font-weight:700; color:#f1f5f9; margin:22px 2px 10px; }}
.rev-title .rsub {{ font-size:11.5px; color:#64748b; font-weight:400; margin-right:8px; }}
.rev-control {{ display:flex; gap:8px; flex-wrap:wrap; align-items:center; background:#111f35; border:1px solid #1e3a5f; border-radius:10px; padding:8px 12px; margin:18px 2px 10px; }}
.rev-control .rc-label {{ font-size:12px; color:#94a3b8; margin-left:4px; }}
.rc-chip {{ background:#0d1a2e; color:#cbd5e1; border:1px solid #2d4668; border-radius:8px; padding:5px 12px; font-family:inherit; font-size:12px; cursor:pointer; transition:all .15s; }}
.rc-chip:hover {{ border-color:#38bdf8; color:#fff; }}
.rc-chip.active {{ background:linear-gradient(135deg,#0d9488,#0f766e); color:#fff; border-color:#0f766e; box-shadow:0 2px 8px rgba(13,148,136,.3); }}
.rev-control .rc-field {{ display:inline-flex; align-items:center; gap:6px; background:#0d1a2e; border:1px solid #2d4668; border-radius:8px; padding:5px 12px; cursor:pointer; user-select:none; transition:border-color .15s; }}
.rev-control .rc-field:hover {{ border-color:#38bdf8; }}
.rev-control .rc-field.open {{ border-color:#0d9488; }}
.rev-control .rc-chev {{ color:#64748b; font-size:10px; }}
.rev-control .rc-val {{ font-size:12.5px; color:#e2e8f0; min-width:64px; text-align:center; }}
.rev-control .rc-sep {{ color:#64748b; font-size:12px; }}
.cal-pop {{ position:fixed; z-index:60; background:#111f35; border:1px solid #2d4668; border-radius:12px; box-shadow:0 14px 44px rgba(0,0,0,.55); padding:12px; width:264px; }}
.cal-pop-head {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:9px; }}
.cal-pop-title {{ font-size:13px; font-weight:700; color:#e2e8f0; }}
.cal-pop-nav {{ background:#0d1a2e; color:#cbd5e1; border:1px solid #2d4668; border-radius:6px; width:27px; height:27px; cursor:pointer; font-size:14px; line-height:1; transition:all .15s; }}
.cal-pop-nav:hover:not(:disabled) {{ border-color:#38bdf8; color:#fff; }}
.cal-pop-nav:disabled {{ opacity:.3; cursor:default; }}
.cal-pop-grid {{ display:grid; grid-template-columns:repeat(7,1fr); gap:2px; }}
.cal-pop-wd {{ text-align:center; font-size:10px; color:#64748b; padding:3px 0; }}
.cal-pop-day {{ text-align:center; font-size:12px; color:#cbd5e1; background:#0d1a2e; border:none; border-radius:6px; padding:5px 0; cursor:pointer; font-family:Consolas,monospace; transition:background .12s; }}
.cal-pop-day:hover:not(:disabled) {{ background:#15243f; color:#fff; }}
.cal-pop-day:disabled {{ color:#3a4970; cursor:default; background:transparent; }}
.cal-pop-day.fri {{ color:#f87171; }}
.cal-pop-day.fri:disabled {{ color:#50303c; }}
.cal-pop-day.inrange {{ background:#123b52; color:#7dd3fc; }}
.cal-pop-day.sel {{ background:linear-gradient(135deg,#0d9488,#0f766e); color:#fff; font-weight:700; }}
.cal-pop-day.sel.fri {{ color:#fff; }}
table.rev {{ width:100%; border-collapse:collapse; font-size:12.5px; min-width:780px; }}
table.rev th, table.rev td {{ border-bottom:1px solid #1e3a5f; padding:9px 10px; text-align:center; }}
table.rev thead th {{ background:#132a47; color:#cbd5e1; font-weight:600; cursor:pointer; user-select:none; white-space:nowrap; position:sticky; top:0; z-index:4; }}
table.rev thead th .arrow {{ color:#38bdf8; font-size:10px; margin-right:3px; }}
table.rev tbody tr:hover {{ background:#15243f; }}
table.rev tr.rank-1 {{ background:rgba(245,158,11,.07); }}
table.rev tr.rank-2 {{ background:rgba(148,163,184,.07); }}
table.rev tr.rank-3 {{ background:rgba(180,83,9,.07); }}
table.rev td.hc {{ text-align:right; }}
table.rev .en {{ font-family:Consolas,monospace; direction:ltr; unicode-bidi:embed; }}
table.rev .medal {{ font-size:13px; }}
table.rev .rank-num {{ color:#64748b; font-weight:700; }}
table.rev .chev {{ color:#38bdf8; font-size:11px; }}
table.rev .hrev-row {{ cursor:pointer; }}
table.rev .hrev-detail td {{ background:#0f1f36; padding:10px 16px; text-align:right; }}
.nrow {{ display:flex; gap:10px; align-items:center; padding:4px 0; border-bottom:1px dashed #1a2946; flex-wrap:wrap; }}
.nrow:last-child {{ border-bottom:none; }}
.np {{ color:#34d399; font-weight:700; }}
.nnet {{ color:#34d399; font-weight:800; }}
</style>
</head>
<body>
<div class='wrap'>
<header>
  <div class='hrow'>
    <div>
      <h1><span class='radar'>🛰️ رادار رقبا</span> — جاجیگا</h1>
      <div class='sub'>{JM[jm-1]} {jy} تا {JM[hor_m-1]} {hor_y} · {len(rooms)} اتاق · به‌روزرسانی: {today.isoformat()} · {len(past_days)} روز گذشته ثبت‌شده</div>
    </div>
    <div class='hd-actions'>
      <button id='exportPastBtn' class='export-btn past-btn' title='خروجی اکسل از جدول دیتابیس (روزهای گذشته)'>📥 اکسل دیتابیس</button>
      <button id='exportBtn' class='export-btn' title='خروجی اکسل از جدول تقویم (روزهای آینده)'>📥 اکسل تقویم</button>
    </div>
  </div>
</header>
<div class='tabs'>
  <button class='tab-btn' data-tab='past'>🗄️ دیتابیس</button>
  <button class='tab-btn active' data-tab='future'>📅 تقویم</button>
</div>
<div id='tab-past' class='tab-pane'>
<div class='stats'>
  <div class='stat'><b>{len(past_days)}</b><span>روز ثبت‌شده</span></div>
  <div class='stat'><b>{past_stats['booked']}</b><span>شب پر</span></div>
  <div class='stat'><b>{past_stats['blocked']}</b><span>بسته میزبان</span></div>
  <div class='stat'><b>{past_stats['free']}</b><span>شب خالی</span></div>
  <div class='stat'><b>{past_stats['half']}</b><span>نیمه‌پر</span></div>
  <div class='stat'><b>{past_stats['nodata']}</b><span>بدون داده</span></div>
  <div class='stat'><b>{past_stats['notracked']}</b><span>از بعد رصد</span></div>
</div>
{legend_past}
<div class='table-wrap'>
{past_table}
</div>
</div>
<div id='tab-future' class='tab-pane active'>
{legend}
<div class='table-wrap'>
<table class='cal'>
<thead>
{month_rows}
<tr class='dayrow'>{''.join(th_cells)}<th class='m'>۳۰ روز</th><th class='m'>۶۰ روز</th><th class='m'>۹۰ روز</th><th class='m'>میانگین شب</th><th class='m'>تخفیف</th><th class='m'>پیک</th></tr>
</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</div>
<div class='rev-control'>
  <span class='rc-label'>دوره محاسبه درآمد:</span>
  <div class='rc-field' id='revFromField' title='از تاریخ — کلیک برای باز کردن تقویم'><span class='rc-val en' id='revFromVal'>—</span><span class='rc-chev'>▾</span></div>
  <span class='rc-sep'>تا</span>
  <div class='rc-field' id='revToField' title='تا تاریخ — کلیک برای باز کردن تقویم'><span class='rc-val en' id='revToVal'>—</span><span class='rc-chev'>▾</span></div>
  {chips_html}
</div>
<div class='rev-title'>💰 تخمین درآمد میزبان‌ها <span class='rsub'>شب‌های پرِ آینده (تا {jalali_str(horizon_day.isoformat())}) · کمیسیون ۱۲٪ · مجموع خالص: {tot_rev_net:,} تومان</span></div>
<div class='table-wrap'>
<table class='rev'>
<thead>
<tr>
  <th data-revkey='rank'>رتبه <span class='arrow'></span></th>
  <th data-revkey='host'>نام میزبان <span class='arrow'></span></th>
  <th data-revkey='rooms'>تعداد اقامتگاه <span class='arrow'></span></th>
  <th data-revkey='booked'>شب‌های پر <span class='arrow'></span></th>
  <th data-revkey='gross'>ناخالص (تومان) <span class='arrow'></span></th>
  <th data-revkey='discount'>تخفیف (تومان) <span class='arrow'></span></th>
  <th data-revkey='commission'>کمیسیون (تومان) <span class='arrow'></span></th>
  <th data-revkey='net'>خالص (تومان) <span class='arrow'></span></th>
  <th>جزئیات</th>
</tr>
</thead>
<tbody id='revHostTbody'></tbody>
</table>
</div>
</div>
<script src="{XLSX_CDN}"></script>
<script>
(function(){{
  var btns = document.querySelectorAll('.tab-btn');
  var past = document.getElementById('tab-past');
  var fut = document.getElementById('tab-future');
  var exp = document.getElementById('exportBtn');
  var expP = document.getElementById('exportPastBtn');
  function show(name){{
    btns.forEach(function(b){{ b.classList.toggle('active', b.getAttribute('data-tab') === name); }});
    past.classList.toggle('active', name === 'past');
    fut.classList.toggle('active', name === 'future');
    if (exp) exp.style.display = name === 'future' ? '' : 'none';
    if (expP) expP.style.display = name === 'past' ? '' : 'none';
  }}
  btns.forEach(function(b){{ b.addEventListener('click', function(){{ show(b.getAttribute('data-tab')); }}); }});
  show('future');
}})();
</script>
{export_js}
{past_export_js}
{edit_js}
{rev_js}
</div>
</body>
</html>"""

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Wrote {OUT} ({len(html):,} bytes) | {len(rooms)} rooms | {len(days_flat)} day columns")


if __name__ == '__main__':
    build()
