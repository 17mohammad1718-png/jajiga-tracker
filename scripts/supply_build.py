#!/usr/bin/env python3
"""
supply_build.py — ساخت دیتاست عرضه بابلکنار + تزریق در supply-dashboard.html
===========================================================================
منابع:
    - data/hosts-babolkenar.json  → میزبان‌ها + member_since + اتاق‌ها
    - data/supply/room-dates.json → تاریخ تخمینی ساخت هر اتاق (supply_backfill)
    - data/all-cabins.json        → روستای پیگیری‌شده (tracked)

خروجی:
    - data/supply-data.json           (payload کامل)
    - supply-dashboard.html           (تزریق JSON به جای علامت /*__SUPPLY_DATA__*/)

نکته: سری ماهانه بر اساس تاریخ شمسی (g2j — همان تابع تأییدشده از
hosts-dashboard v3.1: 2019-06-20 → خرداد 1398).

Usage:
    python scripts/supply_build.py
"""
import json
import os
import re
import sys
from collections import defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOSTS_PATH = os.path.join(PROJECT_ROOT, "data", "hosts-babolkenar.json")
DATES_PATH = os.path.join(PROJECT_ROOT, "data", "supply", "room-dates.json")
CABINS_PATH = os.path.join(PROJECT_ROOT, "data", "all-cabins.json")
OUT_JSON = os.path.join(PROJECT_ROOT, "data", "supply-data.json")
OUT_HTML = os.path.join(PROJECT_ROOT, "supply-dashboard.html")

JM = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
      "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def g2j(gy, gm, gd):
    """Gregorian → Jalali (verified: 2019-06-20 → 1398/3/30, 2026-03-07 → 1404/12/16)."""
    gdm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    d = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + gdm[gm - 1]
    jy = -1595 + 33 * (d // 12053)
    d %= 12053
    jy += 4 * (d // 1461)
    d %= 1461
    if d > 365:
        jy += (d - 1) // 365
        d = (d - 1) % 365
    if d < 186:
        jm = 1 + d // 31
    else:
        jm = 7 + (d - 186) // 30
    return jy, jm


def month_key_iso(iso_date):
    """'2026-04-09' → '2026-04'"""
    return iso_date[:7] if iso_date else None


def jalali_label(iso_date):
    if not iso_date:
        return "نامشخص"
    y, m = int(iso_date[:4]), int(iso_date[5:7])
    jy, jm = g2j(y, m, 1)
    return f"{JM[jm - 1]} {jy}"


# Longest patterns FIRST — کاردگرکلا before کاردرکلا (substring trap).
VILLAGE_PATTERNS = [
    ("سیدکلا", ["سیدکلا", "سید کلا"]),
    ("قرآن تالار", ["قرآن تالار", "قران تالار", "قرآن تلار", "قران تلار"]),
    ("گونه کلا", ["گونه کلا", "گونهکلا"]),
    ("شیردارکلا", ["شیردارکلا", "شیردار کلا"]),
    ("کاردرکلا", ["کاردرکلا", "کاردر کلا", "کاردگرکلا", "کاردگر کلا", "کاردکلا", "کادرکلا"]),
    ("فرامرزکلا", ["فرامرزکلا", "فرامرز کلا"]),
    ("مرزیکلا", ["مرزیکلا", "مرزی کلا"]),
    ("درازکلا", ["درازکلا", "دراز کلا"]),
    ("بالفکلا", ["بالفکلا", "بالف کلا"]),
    ("درونکلا", ["درونکلا", "درون کلا"]),
    ("رئیسکلا", ["رئیسکلا", "رییسکلا", "رئیس کلا"]),
    ("کلاریکلا", ["کلاریکلا", "کلاری کلا"]),
    ("کبریاکلا", ["کبریاکلا", "کبریا کلا"]),
    ("بزچفت", ["بزچفت"]),
    ("ممرزکن", ["ممرزکن"]),
    ("امیرکلا", ["امیرکلا", "امیر کلا"]),
    ("سیادرکلا", ["سیادرکلا", "سیادر کلا"]),
    ("قادیکلا", ["قادیکلا", "قادی کلا"]),
    ("چهره", ["چهره"]),
]

TRACKED_VILLAGES = ["سیدکلا", "قرآن تالار", "گونه کلا", "شیردارکلا", "کاردرکلا", "امیرکلا"]


def assign_village(title):
    """Longest-pattern-first village assignment. Returns village name or 'سایر'."""
    t = title or ""
    # sort patterns by length desc for substring safety
    cands = []
    for vname, pats in VILLAGE_PATTERNS:
        for p in pats:
            cands.append((len(p), vname, p))
    cands.sort(key=lambda x: -x[0])
    for _, vname, p in cands:
        if p in t:
            return vname
    return "سایر"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build():
    hosts_db = load_json(HOSTS_PATH)
    dates = load_json(DATES_PATH) if os.path.exists(DATES_PATH) else {}
    cabins_db = load_json(CABINS_PATH) if os.path.exists(CABINS_PATH) else {}

    tracked_ids = set()
    for v, cabs in cabins_db.get("villages", {}).items():
        for c in cabs:
            tracked_ids.add(int(c["id"]))

    hosts = []
    rooms = []
    host_map = {}

    for h in hosts_db.get("hosts", []):
        rec = {
            "id": str(h.get("id")),
            "name": h.get("name") or "",
            "member_since": h.get("member_since"),
            "rooms_count": len(h.get("rooms", [])),
            "total_books": h.get("total_success_books") or 0,
            "host_level": h.get("host_level") or "مبتدی",
            "j_since": jalali_label(h.get("member_since")),
            "first_room_date": None,
        }
        host_map[rec["id"]] = rec
        hosts.append(rec)

        for r in h.get("rooms", []):
            rid = int(r["id"])
            est = (dates.get(str(rid)) or {}).get("est_date")
            rooms.append({
                "id": rid,
                "title": r.get("title") or "",
                "village": assign_village(r.get("title") or ""),
                "host_id": str(h.get("id")),
                "host_name": h.get("name") or "",
                "member_since": h.get("member_since"),
                "est_date": est,
                "j_est": jalali_label(est),
                "status": (dates.get(str(rid)) or {}).get("status", "active"),
                "price": r.get("price"),
                "success_books": r.get("success_books") or 0,
                "tracked": rid in tracked_ids,
            })
            # first room date per host
            if est and (rec["first_room_date"] is None or est < rec["first_room_date"]):
                rec["first_room_date"] = est

    # Monthly series: hosts by member_since, rooms by est_date
    months = defaultdict(lambda: {"hosts_new": 0, "rooms_new": 0})
    for h in hosts:
        k = month_key_iso(h["member_since"])
        if k:
            months[k]["hosts_new"] += 1
    for r in rooms:
        k = month_key_iso(r["est_date"])
        if k:
            months[k]["rooms_new"] += 1

    series = []
    hosts_cum = rooms_cum = 0
    for k in sorted(months.keys()):
        m = months[k]
        hosts_cum += m["hosts_new"]
        rooms_cum += m["rooms_new"]
        series.append({
            "key": k,
            "j": jalali_label(k + "-01"),
            "hosts_new": m["hosts_new"],
            "rooms_new": m["rooms_new"],
            "hosts_cum": hosts_cum,
            "rooms_cum": rooms_cum,
        })

    # village stats
    vstat = defaultdict(lambda: {"count": 0, "added_2026": 0})
    for r in rooms:
        vstat[r["village"]]["count"] += 1
        if r["est_date"] and r["est_date"][:4] == "2026":
            vstat[r["village"]]["added_2026"] += 1
    village_stats = [
        {"name": k, "count": v["count"], "added_2026": v["added_2026"]}
        for k, v in sorted(vstat.items(), key=lambda x: -x[1]["count"])
    ]

    # sort: newest first by date (default order); undated always last
    def sort_newest(objs, key):
        dated = [o for o in objs if o.get(key)]
        undated = [o for o in objs if not o.get(key)]
        dated.sort(key=lambda o: o[key], reverse=True)
        return dated + undated

    hosts_sorted = sort_newest(hosts, "member_since")
    rooms_sorted = sort_newest(rooms, "est_date")

    dated_rooms = sum(1 for r in rooms if r["est_date"])
    dated_hosts = sum(1 for h in hosts if h["member_since"])
    all_est = [r["est_date"] for r in rooms if r["est_date"]]

    payload = {
        "meta": {
            "built_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "region": "بابلکنار (مازندران)",
            "hosts_total": len(hosts),
            "rooms_total": len(rooms),
            "rooms_dated": dated_rooms,
            "rooms_undated": len(rooms) - dated_rooms,
            "hosts_dated": dated_hosts,
            "date_min": min(all_est) if all_est else None,
            "date_max": max(all_est) if all_est else None,
            "tracked_villages": TRACKED_VILLAGES,
        },
        "hosts": hosts_sorted,
        "rooms": rooms_sorted,
        "months": series,
        "village_stats": village_stats,
    }
    return payload


def inject(payload):
    raw = json.dumps(payload, ensure_ascii=False)
    raw = raw.replace("</", "<\\/")  # safe inside <script type="application/json">
    with open(OUT_HTML, encoding="utf-8") as f:
        html = f.read()
    # Replace the whole JSON block between the script tags (idempotent).
    pattern = r'(<script type="application/json" id="supplyData">\s*).*?(\s*</script>)'
    new_html, count = re.subn(pattern, lambda m: m.group(1) + raw + m.group(2), html, flags=re.DOTALL)
    if count == 0:
        print(f"ERROR: supplyData block not found in {OUT_HTML}", file=sys.stderr)
        sys.exit(1)
    if count > 1:
        print(f"WARNING: replaced {count} supplyData blocks (expected 1)", file=sys.stderr)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(new_html)
    print(f"Injected {len(raw)} chars into {OUT_HTML}")


def main():
    payload = build()
    m = payload["meta"]
    print(f"hosts={m['hosts_total']} rooms={m['rooms_total']} "
          f"dated_rooms={m['rooms_dated']} undated={m['rooms_undated']} "
          f"range={m['date_min']}..{m['date_max']}")
    print("months:", len(payload["months"]))
    print("village_stats:", [(v['name'], v['count']) for v in payload['village_stats'][:8]])
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("wrote", OUT_JSON)
    inject(payload)


if __name__ == "__main__":
    main()
