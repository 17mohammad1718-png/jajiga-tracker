#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fair_band.py — باند قیمت منصفانه در هر دو بازه (آخرهفته + وسطهفته)، معادل دو-شب و شبانه
همان فیلتر مشابه‌های winners_dna بخش ۴: سیدکلا یا متراژ 70-130 و ظرفیت پایه 4-5، قیمت‌دار
خروجی: exports/competitive_2026-09-08/analysis/fair_bands.json
"""
import json
import os

ROOT = r"H:/projects/jajiga-tracker"
ANA = os.path.join(ROOT, "exports", "competitive_2026-09-08", "analysis")
OWN_ID = "3297585"

rooms = json.load(open(os.path.join(ANA, "analysis_rooms.json"), encoding="utf-8"))

def pctile(vals, p):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    i = max(0, min(len(v) - 1, round((len(v) - 1) * p / 100)))
    return v[i]

def band(window_key):
    comps = [r for r in rooms
             if r["دسته"] == "main" and r["شناسه"] != OWN_ID
             and ((r["روستا"] == "سیدکلا" and r["روستا_مطمئن"])
                  or (r.get("متراژ_بنا") and 70 <= r["متراژ_بنا"] <= 130
                      and r.get("ظرفیت_پایه") in (4, 5)))
             and r.get(window_key) is not None]
    prices = [r[window_key] for r in comps]
    out = {"n": len(prices),
           "two_night": {"p25": pctile(prices, 25), "p50": pctile(prices, 50),
                          "p75": pctile(prices, 75)},
           "comp_ids": sorted(int(r["شناسه"]) for r in comps)}
    for k in ("p25", "p50", "p75"):
        out["per_night"] = out.get("per_night", {})
        # معادل شبانه؛ گرد به هزار تومان
        out["per_night"][k] = round(out["two_night"][k] / 2, -3) if out["two_night"][k] else None
    return out

result = {
    "snapshot_date": "2026-09-08",
    "comps_filter": "main & (seyed-kola-sure | 70<=area<=130 & base_capacity 4-5) & priced",
    "own_room_id": int(OWN_ID),
    "weekend": band("قیمت_دوشب_آخر_هفته"),
    "midweek": band("قیمت_دوشب_وسط_هفته"),
}
dest = os.path.join(ANA, "fair_bands.json")
with open(dest, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

print(json.dumps({k: result[k] for k in ("weekend", "midweek")},
                 ensure_ascii=False, indent=1))
print("[saved]", dest)
