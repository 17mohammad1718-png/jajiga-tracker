#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_master_dashboard.py — builds jajiga-master-dashboard.html (single-file,
7 tabs) from jajiga_master.json. Tab contents mirror the existing dashboards:
overview, cabins, hosts, supply, pricing, radar, revenue. Does NOT modify any
existing dashboard or data file.
"""
import json
import os
import re
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "jajiga_master.json")
OUT = os.path.join(ROOT, "jajiga-master-dashboard.html")

JM = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
WD = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج']

def g2j(gy, gm, gd):
    gdm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    d = 355666 + 365 * gy + gy2 // 4 - gy2 // 100 + gy2 // 400 + gd + gdm[gm - 1]
    jy = -1595 + 33 * (d // 12053); d %= 12053
    jy += 4 * (d // 1461); d %= 1461
    if d > 365:
        jy += (d - 1) // 365; d = (d - 1) % 365
    if d < 186:
        jm = 1 + d // 31; jd = 1 + d % 31
    else:
        jm = 7 + (d - 186) // 30; jd = 1 + (d - 186) % 30
    return jy, jm, jd

def fa_num(n):
    """English digits with Persian thousands separator (٫ is not used — plain comma)."""
    if n is None:
        return "—"
    if isinstance(n, float):
        return f"{n:,.1f}" if n != int(n) else f"{int(n):,}"
    return f"{int(n):,}"

def esc(s):
    if s is None:
        return "—"
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def room_link(rid):
    return f"<a class='lk-room' href='https://www.jajiga.com/room/{rid}' target='_blank'>{rid}</a>"

def host_link(hid, name):
    if not hid:
        return esc(name)
    return f"<a class='lk-host' href='https://jajiga.com/user/{hid}' target='_blank'>{esc(name)}</a>"

def medal(i):
    cls = {0: "rank-gold", 1: "rank-silver", 2: "rank-bronze"}.get(i, "rank-plain")
    return f"<span class='rank {cls}'>{i + 1}</span>"

def jsin(data):
    s = json.dumps(data, ensure_ascii=False)
    return s.replace("</", "<\\/")


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    hosts = d["hosts"]
    rooms = d["rooms"]
    state = d["state"]
    nights_radar = d["nights"].get("radar", {})
    revenue = d["revenue"]
    snapshots = d["snapshots"]
    regions = d["regions"]

    # ---------- helpers over rooms ----------
    def getv(r, k, default=None):
        raw = r.get("raw") if isinstance(r.get("raw"), dict) else {}
        return r.get(k, raw.get(k, default))

    cabins = [r for r in rooms if "cabin" in (r.get("sources") or [])]
    tracked_villages = [x["name"] for x in regions if x.get("tracked")]
    supply_rooms = rooms

    # ================= OVERVIEW =================
    active_rooms = [r for r in rooms if r.get("status") in ("active", None)]
    priced = [r for r in active_rooms if r.get("price")]
    avg_price = sum(r["price"] for r in priced) / len(priced) if priced else 0
    max_books = max((r.get("success_books") or 0) for r in rooms)
    newest = max((r for r in rooms if r.get("est_date")), key=lambda r: r["est_date"], default=None)

    def stat_card(title, value, sub=""):
        return (f"<div class='card'><div class='card-title'>{title}</div>"
                f"<div class='card-value'>{value}</div>"
                f"<div class='card-sub'>{sub}</div></div>")

    src_groups = {}
    for r in rooms:
        key = tuple(sorted(r.get("sources") or []))
        src_groups[key] = src_groups.get(key, 0) + 1
    src_rows = []
    for key, cnt in sorted(src_groups.items(), key=lambda kv: (-len(kv[0]), kv[0])):
        labels = "، ".join({'supply': 'عرضه', 'cabin': 'کلبه', 'pricing': 'قیمت'}.get(x, x) for x in key)
        src_rows.append(f"<tr><td>{esc(labels)}</td><td class='en'>{cnt:,}</td></tr>")

    snap_rows = []
    for sn in snapshots.get("supply", []):
        cnt = len(sn.get("data", {}).get("room_ids", []))
        snap_rows.append(f"<tr><td class='en'>{esc(sn['date'])}</td><td>عرضه</td><td class='en'>{cnt:,}</td></tr>")
    for sn in snapshots.get("radar", []):
        cnt = len(sn.get("data", {}).get("rooms", {}))
        snap_rows.append(f"<tr><td class='en'>{esc(str(sn['date']))}</td><td>رادار</td><td class='en'>{cnt:,}</td></tr>")

    overview = f"""
<div class="tab-pane" id="tab-overview">
  <div class="cards">
    {stat_card('میزبان', '<span class="en">' + fa_num(len(hosts)) + '</span>', 'کل میزبان‌های بابلکنار')}
    {stat_card('کل اتاق‌ها', '<span class="en">' + fa_num(len(rooms)) + '</span>', 'عرضه + کلبه + قیمت')}
    {stat_card('روستاهای ردیابی', '<span class="en">' + fa_num(len(tracked_villages)) + '</span>', '، '.join(esc(v) for v in tracked_villages))}
    {stat_card('میانگین قیمت', '<span class="en">' + fa_num(round(avg_price)) + '</span>', 'تومان — اتاق‌های دارای قیمت')}
    {stat_card('دیتاست قیمت', '<span class="en">' + fa_num(state.get('pricing_meta', {}).get('count', 0)) + '</span>', 'اتاق با جزئیات کامل')}
    {stat_card('رادار رقبا', '<span class="en">' + fa_num(len(nights_radar)) + '</span>', 'اتاق ردیابی‌شده روزانه')}
  </div>
  <div class="two-col">
    <div class="box">
      <h3>منابع هر اتاق</h3>
      <div class="table-wrap"><table class="tbl sortable" data-default-col="1">
        <thead><tr><th data-type="text">منبع</th><th data-type="num">تعداد</th></tr></thead>
        <tbody>{''.join(src_rows)}</tbody></table></div>
    </div>
    <div class="box">
      <h3>اسنپ‌شات‌ها</h3>
      <div class="table-wrap"><table class="tbl sortable" data-default-col="0">
        <thead><tr><th data-type="text">تاریخ</th><th data-type="text">نوع</th><th data-type="num">اتاق‌ها</th></tr></thead>
        <tbody>{''.join(snap_rows)}</tbody></table></div>
    </div>
  </div>
  <div class="box">
    <h3>خلاصه بازار</h3>
    <div class="table-wrap"><table class="tbl">
      <tbody>
        <tr><td>بیشترین رزرو موفق یک اتاق</td><td class="en">{fa_num(max_books)}</td></tr>
        <tr><td>جدیدترین اتاق (تخمین)</td><td>{esc(getv(newest, 'title')) if newest else '—'} <span class="en">({esc(getv(newest, 'est_date')) if newest else ''})</span></td></tr>
        <tr><td>منطقه</td><td>{esc(state.get('supply_meta', {}).get('region', 'بابلکنار (مازندران)'))}</td></tr>
      </tbody></table></div>
  </div>
</div>"""

    # ================= CABINS =================
    def cabin_row(i, r):
        raw = r.get("raw") or {}
        return (f"<tr><td>{medal(i)}</td>"
                f"<td class='t-right'>{room_link(r['id'])}</td>"
                f"<td class='t-right'>{esc(r.get('title'))}</td>"
                f"<td>{esc(r.get('village'))}</td>"
                f"<td class='en'>{fa_num(r.get('price'))}</td>"
                f"<td class='en'>{fa_num(raw.get('floor') or raw.get('floor_area'))}</td>"
                f"<td class='en'>{fa_num(raw.get('rooms'))}</td>"
                f"<td class='en'>{fa_num(raw.get('guests') or raw.get('guest_number') or raw.get('max_guest_number'))}</td>"
                f"<td class='en'>{fa_num(r.get('rating'))}</td>"
                f"<td class='en'>{fa_num(r.get('reviews'))}</td>"
                f"<td class='en'>{fa_num(r.get('success_books'))}</td>"
                f"<td>{host_link(r.get('host_id'), r.get('host_name'))}</td></tr>")

    cabins_sorted = sorted(cabins, key=lambda r: r.get("price") or 0, reverse=True)
    cabins_html = "".join(cabin_row(i, r) for i, r in enumerate(cabins_sorted))

    cabins_tab = f"""
<div class="tab-pane" id="tab-cabins">
  <div class="box">
    <h3>کلبه‌های روستاهای ردیابی <span class="en">({len(cabins)})</span> — مرتب‌شده بر اساس قیمت</h3>
    <div class="table-wrap"><table class="tbl sortable" data-default-col="4" data-default-dir="desc">
      <thead><tr>
        <th data-sortable="false">#</th>
        <th data-type="num">شناسه</th>
        <th data-type="text">عنوان</th>
        <th data-type="text">روستا</th>
        <th data-type="num">قیمت</th>
        <th data-type="num">متراژ</th>
        <th data-type="num">خواب</th>
        <th data-type="num">مهمان</th>
        <th data-type="num">امتیاز</th>
        <th data-type="num">نظرات</th>
        <th data-type="num">رزرو موفق</th>
        <th data-type="text">میزبان</th>
      </tr></thead>
      <tbody>{cabins_html}</tbody></table></div>
  </div>
</div>"""

    # ================= HOSTS =================
    def host_row(i, h):
        rooms_c = h.get("rooms") or []
        return (f"<tr><td>{medal(i)}</td>"
                f"<td>{host_link(h.get('id'), h.get('name'))}</td>"
                f"<td>{esc(h.get('host_level'))}</td>"
                f"<td>{'✓' if h.get('verified') else '—'}</td>"
                f"<td class='en'>{esc(h.get('member_since'))}</td>"
                f"<td class='en'>{fa_num(h.get('accept_rate'))}٪</td>"
                f"<td class='en'>{fa_num(h.get('response_time_min'))}</td>"
                f"<td class='en'>{fa_num(h.get('communication_rate'))}</td>"
                f"<td class='en'>{fa_num(h.get('active_rooms_count'))}</td>"
                f"<td class='en'>{fa_num(len(rooms_c))}</td>"
                f"<td class='en'>{fa_num(h.get('total_success_books'))}</td>"
                f"<td class='en'>{fa_num(h.get('avg_price'))}</td></tr>")

    hosts_sorted = sorted(hosts, key=lambda h: h.get("total_success_books") or 0, reverse=True)
    hosts_html = "".join(host_row(i, h) for i, h in enumerate(hosts_sorted))

    hosts_tab = f"""
<div class="tab-pane" id="tab-hosts">
  <div class="box">
    <h3>میزبان‌ها <span class="en">({len(hosts)})</span> — مرتب‌شده بر اساس رزرو موفق</h3>
    <div class="table-wrap"><table class="tbl sortable" data-default-col="10" data-default-dir="desc">
      <thead><tr>
        <th data-sortable="false">#</th>
        <th data-type="text">نام</th>
        <th data-type="text">سطح</th>
        <th data-type="text">تأیید</th>
        <th data-type="text">عضویت</th>
        <th data-type="num">نرخ پذیرش</th>
        <th data-type="num">پاسخ (دقیقه)</th>
        <th data-type="num">ارتباط</th>
        <th data-type="num">اتاق فعال</th>
        <th data-type="num">کل اتاق‌ها</th>
        <th data-type="num">رزرو موفق</th>
        <th data-type="num">میانگین قیمت</th>
      </tr></thead>
      <tbody>{hosts_html}</tbody></table></div>
  </div>
</div>"""

    # ================= SUPPLY =================
    months = state.get("supply_months", [])
    month_rows = "".join(
        f"<tr><td class='en'>{esc(m.get('j'))}</td><td class='en'>{fa_num(m.get('hosts_new'))}</td>"
        f"<td class='en'>{fa_num(m.get('rooms_new'))}</td><td class='en'>{fa_num(m.get('hosts_cum'))}</td>"
        f"<td class='en'>{fa_num(m.get('rooms_cum'))}</td></tr>"
        for m in months)

    vs = state.get("village_stats", [])
    vs_rows = "".join(
        f"<tr><td>{esc(v.get('name'))}</td><td class='en'>{fa_num(v.get('count'))}</td>"
        f"<td class='en'>{fa_num(v.get('added_2026'))}</td></tr>"
        for v in vs)

    supply_tab = f"""
<div class="tab-pane" id="tab-supply">
  <div class="two-col">
    <div class="box">
      <h3>رشد عرضه — ماهانه</h3>
      <div class="table-wrap tbl-fixed-h"><table class="tbl sortable" data-default-col="4" data-default-dir="desc">
        <thead><tr><th data-type="text">ماه</th><th data-type="num">میزبان جدید</th><th data-type="num">اتاق جدید</th><th data-type="num">میزبان کل</th><th data-type="num">اتاق کل</th></tr></thead>
        <tbody>{month_rows}</tbody></table></div>
    </div>
    <div class="box">
      <h3>آمار روستاها</h3>
      <div class="table-wrap"><table class="tbl sortable" data-default-col="1" data-default-dir="desc">
        <thead><tr><th data-type="text">روستا</th><th data-type="num">اتاق‌ها</th><th data-type="num">افزوده ۱۴۰۵</th></tr></thead>
        <tbody>{vs_rows}</tbody></table></div>
    </div>
  </div>
  <div class="box">
    <h3>همه اتاق‌های عرضه <span class="en">({len(supply_rooms)})</span></h3>
    <div class="table-wrap tbl-fixed-h"><table class="tbl sortable" data-default-col="6" data-default-dir="desc">
      <thead><tr>
        <th data-sortable="false">#</th>
        <th data-type="num">شناسه</th>
        <th data-type="text">عنوان</th>
        <th data-type="text">روستا</th>
        <th data-type="text">میزبان</th>
        <th data-type="text">عضویت</th>
        <th data-type="text">تخمین</th>
        <th data-type="num">قیمت</th>
        <th data-type="num">رزرو موفق</th>
        <th data-type="text">منبع</th>
      </tr></thead>
      <tbody>{''.join(
        '<tr><td>{}</td><td>{}</td><td class="t-right">{}</td><td>{}</td><td>{}</td><td class="en">{}</td><td class="en">{}</td><td class="en">{}</td><td class="en">{}</td><td>{}</td></tr>'.format(
            medal(i), room_link(r["id"]), esc(r.get("title")), esc(r.get("village")), host_link(r.get("host_id"), r.get("host_name")),
            esc(r.get("member_since")), esc(r.get("est_date")), fa_num(r.get("price")), fa_num(r.get("success_books")),
            "، ".join(esc(x) for x in (r.get("sources") or [])))
        for i, r in enumerate(sorted(supply_rooms, key=lambda x: x.get("est_date") or "", reverse=True)))}
      </tbody></table></div>
  </div>
</div>"""

    # ================= PRICING =================
    pricing = state.get("pricing_meta", {})
    pricing_rooms = [r for r in rooms if "pricing" in (r.get("sources") or [])]

    def pricing_row(i, r):
        raw = r.get("raw") or {}
        feat = raw.get("features") or []
        feat_fa = []
        for f in feat:
            t = f.get("title") or f.get("name") if isinstance(f, dict) else f
            if t:
                feat_fa.append(str(t))
        feat_s = esc("، ".join(feat_fa[:6]))
        pool = '✓' if raw.get("pool") else ('—' if "pool" in raw else '')
        jac = '✓' if raw.get("jacuzzi") else ('—' if "jacuzzi" in raw else '')
        return (f"<tr><td>{medal(i)}</td>"
                f"<td>{room_link(r['id'])}</td>"
                f"<td class='t-right'>{esc(r.get('title'))}</td>"
                f"<td>{esc(r.get('village'))}</td>"
                f"<td class='en'>{fa_num(r.get('price'))}</td>"
                f"<td class='en'>{fa_num(raw.get('floor_area'))}</td>"
                f"<td class='en'>{fa_num(raw.get('land_area'))}</td>"
                f"<td class='en'>{fa_num(raw.get('bedrooms'))}</td>"
                f"<td class='en'>{fa_num(raw.get('max_guest_number'))}</td>"
                f"<td>{pool}</td><td>{jac}</td>"
                f"<td class='en'>{fa_num(raw.get('features_count'))}</td>"
                f"<td class='en'>{fa_num(r.get('rating'))}</td>"
                f"<td class='en'>{fa_num(r.get('reviews'))}</td>"
                f"<td class='en'>{fa_num(r.get('success_books'))}</td>"
                f"<td class='t-right'>{feat_s}</td></tr>")

    pricing_sorted = sorted(pricing_rooms, key=lambda r: r.get("price") or 0, reverse=True)
    villages = []
    for r in pricing_sorted:
        v = r.get("village")
        if v and v not in villages:
            villages.append(v)
    chips = "".join(f"<button class='chip active' data-v='all'>همه</button>" + "".join(
        f"<button class='chip' data-v='{esc(v)}'>{esc(v)}</button>" for v in villages))

    pricing_tab = f"""
<div class="tab-pane" id="tab-pricing">
  <div class="box">
    <h3>دیتاست قیمت <span class="en">({len(pricing_sorted)})</span></h3>
    <div class="chips" id="pricing-chips">{chips}</div>
    <div class="table-wrap tbl-fixed-h"><table class="tbl sortable" id="pricing-tbl" data-default-col="4" data-default-dir="desc">
      <thead><tr>
        <th data-sortable="false">#</th>
        <th data-type="num">شناسه</th>
        <th data-type="text">عنوان</th>
        <th data-type="text" data-filter="village">روستا</th>
        <th data-type="num">قیمت</th>
        <th data-type="num">متراژ</th>
        <th data-type="num">زمین</th>
        <th data-type="num">خواب</th>
        <th data-type="num">مهمان</th>
        <th data-type="text">استخر</th>
        <th data-type="text">جکوزی</th>
        <th data-type="num">امکانات</th>
        <th data-type="num">امتیاز</th>
        <th data-type="num">نظرات</th>
        <th data-type="num">رزرو موفق</th>
        <th data-type="text">امکانات</th>
      </tr></thead>
      <tbody>{''.join(pricing_row(i, r) for i, r in enumerate(pricing_sorted))}</tbody></table></div>
  </div>
</div>"""

    # ================= RADAR =================
    today = date.today()
    jy, jm, _ = g2j(today.year, today.month, today.day)

    def month_days(jy, jm):
        days = []
        for off in range(-60, 140):
            dd = date.today() + timedelta(days=off)
            y, m, _ = g2j(dd.year, dd.month, dd.day)
            if y == jy and m == jm:
                days.append(dd)
        return sorted(days)

    radar_months = []  # (label, [date, ...])
    for mm in range(2):
        y = jy if jm + mm <= 12 else jy + 1
        m = ((jm - 1 + mm) % 12) + 1
        days = [d for d in month_days(y, m) if d >= today - timedelta(days=1)]
        if days:
            radar_months.append((f"{JM[m-1]} {y}", days))

    radar_cfg = state.get("radar_config", {})
    radar_rooms_cfg = radar_cfg.get("rooms", [])
    radar_nights_by_date = {}
    for rid, nights in nights_radar.items():
        for n in nights:
            radar_nights_by_date.setdefault(n["date"], {})[rid] = n

    def radar_cell(dstr, rid):
        n = radar_nights_by_date.get(dstr, {}).get(str(rid))
        if not n:
            return "<td class='c nodata'>—</td>"
        if n.get("is_unavailable"):
            return f"<td class='c booked' title='{esc(dstr)} رزرو'>×</td>"
        price = n.get("price")
        disc = n.get("discount") or 0
        if disc:
            cls = "disc"
            title = f"{esc(dstr)} تخفیف {disc}٪"
        else:
            cls = "free"
            title = esc(dstr)
        return f"<td class='c {cls}' title='{title}'>{fa_num(price) if price else '—'}</td>"

    radar_tables = ""
    for label, days in radar_months:
        th = "".join(f"<th class='dayh'>{WD[(d.weekday()+2)%7]}<span class='dnum'>{g2j(d.year, d.month, d.day)[2]}</span></th>" for d in days)
        rows = ""
        for rc in radar_rooms_cfg:
            rid = rc["id"]
            cells = "".join(radar_cell(d.isoformat(), rid) for d in days)
            own = " own" if rc.get("own") else ""
            rows += f"<tr class='rrow{own}'><td class='rlabel'>{esc(rc.get('label'))}<span class='en'>({rid})</span></td>{cells}</tr>"
        radar_tables += f"""
      <div class='radar-month'>
        <h4>{label}</h4>
        <div class="table-wrap"><table class="tbl radar"><thead><tr><th class="rlabel">اتاق</th>{th}</tr></thead><tbody>{rows}</tbody></table></div>
      </div>"""

    radar_sum_rows = ""
    for rc in radar_rooms_cfg:
        rid = str(rc["id"])
        nights = nights_radar.get(rid, [])
        future = [n for n in nights if n["date"] > today.isoformat()]
        booked = sum(1 for n in future if n.get("is_unavailable"))
        free = sum(1 for n in future if not n.get("is_unavailable"))
        prices = [n["price"] for n in future if n.get("price")]
        minp = min(prices) if prices else None
        radar_sum_rows += (f"<tr class='{'own' if rc.get('own') else ''}'><td>{esc(rc.get('label'))}</td>"
                           f"<td class='en'>{esc(rc.get('short_label'))}</td>"
                           f"<td class='en'>{fa_num(minp)}</td>"
                           f"<td class='en'>{booked}</td><td class='en'>{free}</td></tr>")

    radar_tab = f"""
<div class="tab-pane" id="tab-radar">
  <div class="box">
    <h3>رادار رقبا — تقویم دو ماه شمسی <span class="en">({len(radar_rooms_cfg)})</span></h3>
    <div class="legend">
      <span class="lg free">آزاد</span>
      <span class="lg disc">تخفیف</span>
      <span class="lg booked">رزرو شده</span>
      <span class="lg nodata">بدون داده</span>
    </div>
    {radar_tables}
  </div>
  <div class="box">
    <h3>خلاصه آینده (از امروز)</h3>
    <div class="table-wrap"><table class="tbl sortable" data-default-col="4" data-default-dir="desc">
      <thead><tr><th data-type="text">اتاق</th><th data-type="text">کوتاه</th><th data-type="num">کمینه قیمت</th><th data-type="num">رزرو شده</th><th data-type="num">آزاد</th></tr></thead>
      <tbody>{radar_sum_rows}</tbody></table></div>
  </div>
</div>"""

    # ================= REVENUE =================
    rev_sorted = sorted(revenue, key=lambda r: r.get("net") or 0, reverse=True)
    tot = {"booked": 0, "free": 0, "gross": 0, "discount": 0, "commission": 0, "net": 0}
    rev_rows = ""
    for i, r in enumerate(rev_sorted):
        for k in tot:
            tot[k] += r.get(k) or 0
        rev_rows += (f"<tr><td>{medal(i)}</td><td>{room_link(r['id'])}</td>"
                     f"<td class='t-right'>{esc(r.get('title'))}</td>"
                     f"<td>{host_link(r.get('host_id'), r.get('host_name'))}</td>"
                     f"<td class='en'>{fa_num(r.get('booked'))}</td><td class='en'>{fa_num(r.get('free'))}</td>"
                     f"<td class='en'>{fa_num(r.get('gross'))}</td><td class='en'>{fa_num(r.get('discount_total'))}</td>"
                     f"<td class='en'>{fa_num(r.get('commission'))}</td><td class='en'>{fa_num(r.get('net'))}</td></tr>")
    rev_rows += (f"<tr class='tot'><td colspan='4'>جمع کل</td>"
                 f"<td class='en'>{fa_num(tot['booked'])}</td><td class='en'>{fa_num(tot['free'])}</td>"
                 f"<td class='en'>{fa_num(tot['gross'])}</td><td class='en'>{fa_num(tot['discount'])}</td>"
                 f"<td class='en'>{fa_num(tot['commission'])}</td><td class='en'>{fa_num(tot['net'])}</td></tr>")

    revenue_tab = f"""
<div class="tab-pane" id="tab-revenue">
  <div class="box">
    <h3>تخمین درآمد — مرداد ۱۴۰۵ <span class="en">({len(rev_sorted)})</span></h3>
    <div class="table-wrap tbl-fixed-h"><table class="tbl sortable" data-default-col="9" data-default-dir="desc">
      <thead><tr>
        <th data-sortable="false">#</th>
        <th data-type="num">شناسه</th>
        <th data-type="text">عنوان</th>
        <th data-type="text">میزبان</th>
        <th data-type="num">رزرو</th>
        <th data-type="num">آزاد</th>
        <th data-type="num">ناخالص</th>
        <th data-type="num">تخفیف</th>
        <th data-type="num">کمیسیون</th>
        <th data-type="num">خالص</th>
      </tr></thead>
      <tbody>{rev_rows}</tbody></table></div>
  </div>
</div>"""

    # ================= HTML SHELL =================
    days_json = jsin([{"g": d.isoformat(), "j": f"{g2j(d.year, d.month, d.day)[2]} {JM[g2j(d.year, d.month, d.day)[1]-1]}",
                       "wd": WD[(d.weekday()+2)%7]} for _, days in radar_months for d in days])

    html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>داشبورد جامع جاجیگا — بابلکنار</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🗃️</text></svg>">
<style>
:root {{
  --bg:#0f1117; --panel:rgba(22,27,34,.72); --panel-solid:#12161d; --border:#30363d;
  --text:#e6edf3; --muted:#8b949e; --blue:#58a6ff; --orange:#f0883e; --green:#3fb950;
  --gold:#f0b429; --silver:#c9d1d9; --bronze:#d08a5b; --red:#f85149;
}}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ background:var(--bg); color:var(--text); font-family:'Vazirmatn',Tahoma,sans-serif; padding:16px; }}
.en {{ font-family:Consolas,'Courier New',monospace; direction:ltr; unicode-bidi:embed; }}
a {{ color:var(--blue); text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
.lk-room {{ color:var(--blue); }}
.lk-host {{ color:var(--orange); }}
h1 {{ font-size:22px; margin-bottom:4px; }}
.sub {{ color:var(--muted); font-size:13px; margin-bottom:14px; }}
/* tabs */
.tabs {{ display:flex; gap:6px; flex-wrap:wrap; margin-bottom:14px; }}
.tab-btn {{ background:var(--panel); color:var(--muted); border:1px solid var(--border); padding:8px 16px; border-radius:8px; cursor:pointer; font-family:inherit; font-size:14px; }}
.tab-btn:hover {{ color:var(--text); border-color:var(--muted); }}
.tab-btn.active {{ background:var(--blue); color:#0b1117; border-color:var(--blue); font-weight:600; }}
.tab-pane {{ display:none; }}
.tab-pane.active {{ display:block; }}
/* cards */
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; margin-bottom:14px; }}
.card {{ background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:12px; }}
.card-title {{ color:var(--muted); font-size:12px; }}
.card-value {{ font-size:22px; font-weight:700; margin:4px 0; }}
.card-sub {{ color:var(--muted); font-size:11px; }}
/* boxes */
.box {{ background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:12px; margin-bottom:14px; }}
.box h3 {{ font-size:14px; color:var(--text); margin-bottom:10px; }}
.two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
@media (max-width:900px) {{ .two-col {{ grid-template-columns:1fr; }} }}
/* tables */
.table-wrap {{ overflow:auto; max-height:68vh; scrollbar-gutter:stable; scrollbar-width:thin; scrollbar-color:#475569 #0b1526; }}
.table-wrap::-webkit-scrollbar {{ width:10px; height:10px; }}
.table-wrap::-webkit-scrollbar-track {{ background:#0b1526; border-radius:8px; }}
.table-wrap::-webkit-scrollbar-thumb {{ background:linear-gradient(180deg,#475569,#334155); border-radius:8px; border:2px solid #0b1526; }}
.table-wrap::-webkit-scrollbar-thumb:hover {{ background:linear-gradient(180deg,#5b6f8f,#475569); }}
.table-wrap::-webkit-scrollbar-corner {{ background:#0b1526; }}
@media (pointer:fine) {{ .table-wrap {{ scrollbar-width:thin; }} }}
.tbl {{ width:100%; border-collapse:collapse; font-size:13px; }}
.tbl th, .tbl td {{ border-bottom:1px solid var(--border); padding:6px 8px; text-align:center; white-space:nowrap; }}
.tbl thead th {{ position:sticky; top:0; background:var(--panel-solid); z-index:2; color:var(--muted); font-weight:600; cursor:pointer; user-select:none; }}
.tbl thead th.sort-asc::after {{ content:' ▲'; color:var(--green); }}
.tbl thead th.sort-desc::after {{ content:' ▼'; color:var(--green); }}
.tbl tbody tr:hover {{ background:rgba(88,166,255,.06); }}
.tbl .t-right {{ text-align:right; }}
.tbl td.t-right {{ white-space:normal; min-width:180px; }}
.tbl tr.tot td {{ background:rgba(240,180,41,.08); font-weight:700; border-top:2px solid var(--gold); }}
.tbl-fixed-h thead th {{ z-index:3; }}
/* rank medals */
.rank {{ display:inline-block; width:22px; height:22px; line-height:22px; border-radius:50%; font-size:12px; font-weight:700; color:#0b1117; }}
.rank-gold {{ background:var(--gold); }}
.rank-silver {{ background:var(--silver); color:#111; }}
.rank-bronze {{ background:var(--bronze); }}
.rank-plain {{ background:var(--border); color:var(--text); }}
/* radar */
.legend {{ display:flex; gap:12px; margin-bottom:10px; font-size:12px; color:var(--muted); }}
.lg {{ padding:2px 8px; border-radius:6px; border:1px solid var(--border); }}
.lg.free {{ background:rgba(63,185,80,.15); color:var(--green); }}
.lg.disc {{ background:rgba(240,136,62,.15); color:var(--orange); }}
.lg.booked {{ background:rgba(248,81,73,.15); color:var(--red); }}
.lg.nodata {{ background:var(--panel-solid); color:var(--muted); }}
.radar-month {{ margin-bottom:16px; }}
.radar-month h4 {{ font-size:15px; margin-bottom:8px; }}
.tbl.radar {{ font-size:12px; }}
.tbl.radar th.dayh {{ cursor:default; }}
.tbl.radar .dnum {{ display:block; font-family:Consolas,monospace; font-size:10px; color:var(--muted); }}
.tbl.radar td.c {{ min-width:52px; }}
.tbl.radar td.free {{ color:var(--green); }}
.tbl.radar td.disc {{ color:var(--orange); }}
.tbl.radar td.booked {{ color:var(--red); }}
.tbl.radar td.nodata {{ color:var(--muted); opacity:.5; }}
.tbl.radar .rlabel {{ text-align:right; color:var(--muted); font-size:11px; position:sticky; right:0; background:var(--panel-solid); }}
.tbl.radar tr.own .rlabel {{ color:var(--gold); font-weight:700; }}
.tbl.radar tr.own td {{ background:rgba(240,180,41,.05); }}
/* chips */
.chips {{ display:flex; gap:6px; flex-wrap:wrap; margin-bottom:10px; }}
.chip {{ background:var(--panel); border:1px solid var(--border); color:var(--muted); padding:4px 12px; border-radius:14px; cursor:pointer; font-family:inherit; font-size:12px; }}
.chip.active {{ background:var(--blue); color:#0b1117; border-color:var(--blue); }}
@media print {{ .tab-pane {{ display:block !important; }} }}
</style>
</head>
<body>
<h1>داشبورد جامع جاجیگا <span class="en">— بابلکنار</span></h1>
<div class="sub">دیتابیس یگانه · <span class="en">{esc(d['meta'].get('version'))}</span> · ساخته‌شده <span class="en">{esc(d['meta'].get('built_at'))}</span></div>
<div class="tabs">
  <button class="tab-btn active" data-tab="tab-overview">کلیات</button>
  <button class="tab-btn" data-tab="tab-cabins">کلبه‌ها</button>
  <button class="tab-btn" data-tab="tab-hosts">میزبان‌ها</button>
  <button class="tab-btn" data-tab="tab-supply">عرضه</button>
  <button class="tab-btn" data-tab="tab-pricing">قیمت</button>
  <button class="tab-btn" data-tab="tab-radar">رادار رقبا</button>
  <button class="tab-btn" data-tab="tab-revenue">درآمد</button>
</div>
{overview}
{cabins_tab}
{hosts_tab}
{supply_tab}
{pricing_tab}
{radar_tab}
{revenue_tab}
<script>
(function(){{
  // tabs
  var btns = document.querySelectorAll('.tab-btn');
  btns.forEach(function(b){{
    b.addEventListener('click', function(){{
      btns.forEach(function(x){{ x.classList.remove('active'); }});
      document.querySelectorAll('.tab-pane').forEach(function(p){{ p.classList.remove('active'); }});
      b.classList.add('active');
      document.getElementById(b.dataset.tab).classList.add('active');
    }});
  }});
  // sortable tables
  function sortTable(table){{
    var heads = table.querySelectorAll('thead th');
    var tbody = table.querySelector('tbody');
    var state = {{}};
    function numVal(v){{ var n = parseFloat(String(v).replace(/[^0-9.\\-]/g,'')); return isNaN(n) ? -Infinity : n; }}
    function cellText(tr, i){{ return tr.children[i] ? tr.children[i].textContent.trim() : ''; }}
    heads.forEach(function(th, i){{
      if (th.dataset.sortable === 'false') return;
      th.addEventListener('click', function(){{
        var type = th.dataset.type || 'text';
        var dir = state[i] || 0;
        if (dir === 0) dir = 1; else if (dir === 1) dir = 2; else dir = 0;
        state[i] = dir;
        heads.forEach(function(h, j){{ if (j !== i) h.classList.remove('sort-asc','sort-desc'); }});
        th.classList.remove('sort-asc','sort-desc');
        if (dir === 0) {{
          // reset to original order
          Array.prototype.slice.call(tbody.rows).sort(function(a,b){{
            return +a.dataset.orig - +b.dataset.orig;
          }}).forEach(function(r){{ tbody.appendChild(r); }});
          return;
        }}
        th.classList.add(dir === 1 ? 'sort-desc' : 'sort-asc');
        Array.prototype.slice.call(tbody.rows).sort(function(a,b){{
          var va = cellText(a, i), vb = cellText(b, i);
          if (type === 'num') {{ va = numVal(va); vb = numVal(vb); return va - vb; }}
          return String(va).localeCompare(String(vb), 'fa');
        }}).forEach(function(r){{
          // dir 1 = زیاد به کم (desc) ; dir 2 = کم به زیاد (asc)
          if (dir === 1) tbody.insertBefore(r, tbody.firstChild); else tbody.appendChild(r);
        }});
      }});
    }});
  }}
  document.querySelectorAll('table.sortable').forEach(function(t){{
    Array.prototype.slice.call(t.querySelectorAll('tbody tr')).forEach(function(r, i){{ r.dataset.orig = i; }});
    sortTable(t);
    // apply default sort
    var dc = t.dataset.defaultCol;
    if (dc !== undefined) {{
      var head = t.querySelectorAll('thead th')[parseInt(dc, 10)];
      if (head) {{
        var dd = t.dataset.defaultDir || 'desc';
        head.dataset.type = head.dataset.type || 'num';
        var ev = new MouseEvent('click', {{bubbles:true}});
        head.dispatchEvent(ev);
        if (dd === 'asc') {{ head.dispatchEvent(ev); }}
      }}
    }}
  }});
  // pricing village chips
  var chips = document.querySelectorAll('#pricing-chips .chip');
  chips.forEach(function(c){{
    c.addEventListener('click', function(){{
      chips.forEach(function(x){{ x.classList.remove('active'); }});
      c.classList.add('active');
      var v = c.dataset.v;
      var tbl = document.getElementById('pricing-tbl');
      Array.prototype.slice.call(tbl.querySelectorAll('tbody tr')).forEach(function(r){{
        var vcell = r.children[3];
        r.style.display = (v === 'all' || (vcell && vcell.textContent.trim() === v)) ? '' : 'none';
      }});
    }});
  }});
}})();
</script>
</body>
</html>"""

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"jajiga-master-dashboard.html written: {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)")
    print(f"  cabins {len(cabins)} | hosts {len(hosts)} | supply rooms {len(supply_rooms)} | pricing {len(pricing_rooms)} | radar months {len(radar_months)} | revenue {len(rev_sorted)}")


if __name__ == "__main__":
    main()
