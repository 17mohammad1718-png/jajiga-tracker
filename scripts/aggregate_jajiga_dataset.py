#!/usr/bin/env python3
"""
Aggregate ALL jajiga-tracker data into a single machine-readable JSON file.
Goal: zero data loss + AI-friendly structure.

Reads every data source under data/ and writes:
    jajiga_complete_dataset.json

Sections:
  meta          -> provenance + structure guide (generated_at, counts, glossary)
  hosts_db      -> data/hosts-babolkenar.json  ({meta, hosts:[346 hosts w/ rooms]})
  all_cabins    -> data/all-cabins.json        ({meta, villages:{6 villages, 157 cabins}})
  supply        -> data/supply-data.json       (meta, hosts, rooms, months, village_stats)
  room_dates    -> data/supply/room-dates.json (per-room first photo/review/est dates)
  snapshots     -> data/snapshots/*.json       (historical snapshots)
  pricing       -> data/pricing/pricing-dataset.json + .csv (108 cabins aggregated)
  raw_pricing   -> per-village raw API room dumps (118 files, each wrapped with provenance)

All original fields are preserved verbatim. Only additive wrappers (provenance)
are introduced in raw_pricing so the AI can trace each record to its file/village.
"""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data"
OUT = Path(__file__).resolve().parent.parent / "jajiga_complete_dataset.json"

VILLAGE_RAW_DIRS = ["seydkola", "gonehkola", "quran_talar", "shirdarkola", "sample"]


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_csv_rows(path: Path) -> list:
    import csv

    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_raw_village(name: str) -> list:
    """Raw API dumps per village, wrapped with provenance (no data changed)."""
    raw_dir = BASE / "pricing" / f"{name}_raw"
    if not raw_dir.is_dir():
        return []
    out = []
    for fp in sorted(raw_dir.glob("*.json")):
        rec = load_json(fp)
        out.append(
            {
                "village_raw_dir": name,
                "source_file": fp.name,
                "room_id": rec.get("id") if isinstance(rec, dict) else None,
                "data": rec,
            }
        )
    return out


def main() -> int:
    # ------------------------------------------------------------------ meta
    hosts_db = load_json(BASE / "hosts-babolkenar.json")
    all_cabins = load_json(BASE / "all-cabins.json")
    supply = load_json(BASE / "supply-data.json")
    room_dates = load_json(BASE / "supply" / "room-dates.json")
    snapshots = [load_json(p) for p in sorted((BASE / "snapshots").glob("*.json"))]
    pricing_json = load_json(BASE / "pricing" / "pricing-dataset.json")
    pricing_csv = load_csv_rows(BASE / "pricing" / "pricing-dataset.csv")
    raw_pricing = {name: load_raw_village(name) for name in VILLAGE_RAW_DIRS}

    hosts = hosts_db.get("hosts", [])
    villages = all_cabins.get("villages", {})
    cabin_count = sum(len(v) for v in villages.values())

    # ------------------------------------------------------------- assemble
    doc = {
        "meta": {
            "project": "jajiga-tracker",
            "region": "Babolkenar (Mazandaran), Babol — Swiss chalets / cottages",
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "purpose": "Complete lossless aggregation of every data file in the "
                       "jajiga-tracker project, structured for efficient AI reading.",
            "structure_guide": {
                "hosts_db": "dict {meta, hosts[346]} — full host profiles with embedded rooms (from /api/user/{id})",
                "all_cabins": "dict {meta, villages{...}} — 157 curated cabins across 6 villages with occupancy stats",
                "supply": "dict {meta, hosts[346], rooms[467], months[68], village_stats} — supply timeline growth data",
                "room_dates": "dict {room_id → {id,title,host_created_at,first_photo,first_review,est_date}}",
                "snapshots": "list of snapshot dicts — historical point-in-time supply captures",
                "pricing": "dict {json[108 cabins], csv[108 rows as dicts]} — aggregated pricing factors dataset",
                "raw_pricing": "dict {village_raw_dir -> [{village_raw_dir, source_file, room_id, data{full /api/room/{id} dump}}]}",
            },
            "counts": {
                "hosts_db_hosts": len(hosts),
                "all_cabins_total": cabin_count,
                "all_cabins_villages": list(villages.keys()),
                "supply_hosts": len(supply.get("hosts", [])),
                "supply_rooms": len(supply.get("rooms", [])),
                "supply_months": len(supply.get("months", [])),
                "room_dates_rooms": len(room_dates),
                "snapshots": len(snapshots),
                "pricing_cabins_json": len(pricing_json),
                "pricing_cabins_csv": len(pricing_csv),
                "raw_pricing_files": {k: len(v) for k, v in raw_pricing.items()},
                "raw_pricing_total": sum(len(v) for v in raw_pricing.values()),
            },
        },
        "hosts_db": hosts_db,
        "all_cabins": all_cabins,
        "supply": supply,
        "room_dates": room_dates,
        "snapshots": snapshots,
        "pricing": {
            "json": pricing_json,
            "csv": pricing_csv,
        },
        "raw_pricing": raw_pricing,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    total_raw = sum(len(v) for v in raw_pricing.values())
    print(f"✅ Aggregated dataset written to {OUT}")
    print(f"   hosts_db hosts : {len(hosts)}")
    print(f"   all_cabins     : {cabin_count} cabins in {len(villages)} villages")
    print(f"   supply         : {len(supply.get('hosts', []))} hosts / {len(supply.get('rooms', []))} rooms")
    print(f"   room_dates     : {len(room_dates)} rooms")
    print(f"   snapshots      : {len(snapshots)}")
    print(f"   pricing        : {len(pricing_json)} cabins (json) / {len(pricing_csv)} rows (csv)")
    print(f"   raw_pricing    : {total_raw} files across {len(raw_pricing)} villages")
    print(f"   file size      : {OUT.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    sys.exit(main())