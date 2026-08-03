#!/usr/bin/env python3
"""
Verify the aggregated dataset against original sources.
Returns 0 if all checks pass, non-zero if any mismatch.
"""
import json
import csv
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data"
AGG = Path(__file__).resolve().parent.parent / "jajiga_complete_dataset.json"

def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_csv_rows(path: Path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def main() -> int:
    try:
        agg = load_json(AGG)
    except Exception as e:
        print(f"❌ Cannot read aggregated dataset: {e}")
        return 1

    errors = []
    warnings = []

    # ---------- hosts_db ----------
    hosts_src = load_json(BASE / "hosts-babolkenar.json")
    if agg.get("hosts_db") != hosts_src:
        errors.append("hosts_db mismatch")
    else:
        print("✓ hosts_db matches")

    # ---------- all_cabins ----------
    all_cabins_src = load_json(BASE / "all-cabins.json")
    if agg.get("all_cabins") != all_cabins_src:
        errors.append("all_cabins mismatch")
    else:
        print("✓ all_cabins matches")

    # ---------- supply ----------
    supply_src = load_json(BASE / "supply-data.json")
    if agg.get("supply") != supply_src:
        errors.append("supply mismatch")
    else:
        print("✓ supply matches")

    # ---------- room_dates ----------
    room_dates_src = load_json(BASE / "supply" / "room-dates.json")
    if agg.get("room_dates") != room_dates_src:
        errors.append("room_dates mismatch")
    else:
        print("✓ room_dates matches")

    # ---------- snapshots ----------
    snapshots_dir = BASE / "snapshots"
    snapshots_src = [load_json(p) for p in sorted(snapshots_dir.glob("*.json"))]
    if agg.get("snapshots") != snapshots_src:
        errors.append("snapshots mismatch")
    else:
        print(f"✓ snapshots count {len(snapshots_src)} matches")

    # ---------- pricing ----------
    pricing_json_src = load_json(BASE / "pricing" / "pricing-dataset.json")
    pricing_csv_src = load_csv_rows(BASE / "pricing" / "pricing-dataset.csv")
    pricing_agg = agg.get("pricing", {})
    if pricing_agg.get("json") != pricing_json_src:
        errors.append("pricing json mismatch")
    else:
        print("✓ pricing json matches")
    if pricing_agg.get("csv") != pricing_csv_src:
        errors.append("pricing csv mismatch")
    else:
        print("✓ pricing csv matches")

    # ---------- raw_pricing ----------
    villages = ["seydkola", "gonehkola", "quran_talar", "shirdarkola", "sample"]
    for v in villages:
        raw_dir = BASE / "pricing" / f"{v}_raw"
        src_files = sorted(raw_dir.glob("*.json")) if raw_dir.is_dir() else []
        src_data = [load_json(fp) for fp in src_files]
        agg_village = agg.get("raw_pricing", {}).get(v, [])
        # Compare only the data field (ignore wrapper fields)
        agg_data_only = [item.get("data") for item in agg_village if isinstance(item, dict)]
        if src_data != agg_data_only:
            errors.append(f"raw_pricing {v} mismatch: expected {len(src_data)} files, got {len(agg_data_only)}")
        else:
            print(f"✓ raw_pricing {v} count {len(src_data)} matches")

    if errors:
        print("\n❌ Verification failed:")
        for e in errors:
            print(" -", e)
        return 1
    else:
        print("\n✅ All checks passed. No data loss detected.")
        return 0

if __name__ == "__main__":
    sys.exit(main())