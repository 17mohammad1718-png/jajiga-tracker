# Aggregate Jajiga Tracker Dataset Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Create a single machine-readable JSON file containing all data from the jajiga-tracker project, preserving every detail for optimal AI consumption.

**Architecture:** Inventory all data sources, design a normalized JSON structure that groups data by entity (hosts, rooms, raw pricing, supply timeline, etc.), write a Python script to load and merge sources, validate completeness, and output the final dataset.

**Tech Stack:** Python 3.11, standard library (json, os, pathlib), no external dependencies.

---

### Task 1: Inventory all data files

**Objective:** List every data file in the project to ensure none are missed.

**Files:** 
- Read: `data/hosts-babolkenar.json`
- Read: `data/all-cabins.json`
- Read: `data/supply-data.json`
- Read: `data/supply/room-dates.json`
- Read: `data/snapshots/supply-2026-08-01.json`
- Read: `data/pricing/pricing-dataset.json`
- Read: `data/pricing/pricing-dataset.csv`
- Read: each village raw pricing folder: `data/pricing/seydkola_raw/*.json`, `data/pricing/gonehkola_raw/*.json`, `data/pricing/quran_talar_raw/*.json`, `data/pricing/shirdarkola_raw/*.json`, `data/pricing/sample_raw/*.json`
- Optionally: check for any other `.json` or `.csv` files in `data/` and subdirectories.

**Step 1: Write inventory script**
```python
import json, os, csv, glob
from pathlib import Path

def inventory():
    base = Path('data')
    files = []
    for p in base.rglob('*'):
        if p.is_file() and p.suffix in ['.json', '.csv']:
            files.append(str(p))
    return sorted(files)

if __name__ == '__main__':
    for f in inventory():
        print(f)
```

**Step 2: Run script to verify list**
Run: `python -c "import inventory; inventory.inventory()"` (or execute the script)
Expected: list of all data files with relative paths.

**Step 3: Commit**
```bash
git add .hermes/plans/2026-08-01_aggregate_jajiga_data.md
git commit -m "plan: create aggregation plan for jajiga dataset"
```

---

### Task 2: Design target JSON schema

**Objective:** Define the structure of the final aggregated JSON.

**Files:** None (design only).

**Step 1: Outline schema**
Top-level keys:
- `meta`: overall metadata (generated timestamp, source, version, counts)
- `hosts`: list of host objects from `hosts-babolkenar.json` (each host may include a `rooms` sublist if we choose to embed)
- `rooms`: list of room objects from `supply-data.json` (or we could rely on host.rooms; we'll keep both for flexibility)
- `raw_pricing`: dict keyed by village name (seydkola, gonehkola, quran_talar, shirdarkola, sample) each containing list of raw room API responses
- `aggregated_pricing`: object with `json` (pricing-dataset.json) and `csv` (pricing-dataset.csv as list of rows)
- `supply`: object containing `hosts` (from supply-data.json hosts), `rooms` (from supply-data.json rooms), `months`, `village_stats`
- `room_dates`: object from `supply/room-dates.json`
- `snapshots`: list of snapshot objects (currently just one for 2026-08-01)
- `all_cabins`: object from `data/all-cabins.json` (meta and villages)

We'll also consider embedding rooms inside hosts to avoid duplication, but we'll keep both for query flexibility.

**Step 2: Write schema description to a temporary file for reference**
```python
schema = {
    "meta": {"generated_at": "ISO timestamp", "source": "jajiga-tracker", "version": "1.0"},
    "hosts": [...],
    "rooms": [...],
    "raw_pricing": {"seydkola": [...], "gonehkola": [...], ...},
    "aggregated_pricing": {"json": {...}, "csv": [..., ...]},
    "supply": {"hosts": [...], "rooms": [...], "months": [...], "village_stats": [...]},
    "room_dates": {...},
    "snapshots": [...],
    "all_cabins": {...}
}
```
(No code to run; just documentation.)

**Step 3: Commit** (no actual file change, but we can note in plan)

---

### Task 3: Write aggregation script

**Objective:** Create a Python script that loads all sources and outputs the aggregated JSON.

**Files:** 
- Create: `scripts/aggregate_jajiga_dataset.py`
- Modify: none (read-only on data files)

**Step 1: Write script**
```python
#!/usr/bin/env python3
"""
Aggregate all jajiga-tracker data into a single JSON file.
Output: jajiga_complete_dataset.json
"""
import json
import csv
from pathlib import Path
from datetime import datetime, timezone

BASE = Path('data')

def load_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def load_csv_as_dicts(p):
    with open(p, encoding='utf-8') as f:
        return list(csv.DictReader(f))

def main():
    out = {}

    # meta
    out['meta'] = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'source': 'jajiga-tracker',
        'version': '1.0',
        'note': 'Complete aggregation of all data files in the project.'
    }

    # hosts-babolkenar.json
    hosts_path = BASE / 'hosts-babolkenar.json'
    out['hosts'] = load_json(hosts_path)  # expects dict with meta and hosts? Actually file is {'meta':..., 'hosts':[...]}
    # The file contains meta and hosts; we'll keep the whole object? Let's extract just hosts list.
    # But to preserve meta, we could keep it under hosts.meta. Let's do:
    hosts_data = load_json(hosts_path)
    out['hosts'] = hosts_data.get('hosts', [])
    out['hosts_meta'] = hosts_data.get('meta', {})

    # all-cabins.json
    all_cabins_path = BASE / 'all-cabins.json'
    out['all_cabins'] = load_json(all_cabins_path)

    # supply-data.json
    supply_path = BASE / 'supply-data.json'
    supply_data = load_json(supply_path)
    out['supply'] = {
        'meta': supply_data.get('meta', {}),
        'hosts': supply_data.get('hosts', []),
        'rooms': supply_data.get('rooms', []),
        'months': supply_data.get('months', []),
        'village_stats': supply_data.get('village_stats', [])
    }

    # room-dates.json
    room_dates_path = BASE / 'supply' / 'room-dates.json'
    out['room_dates'] = load_json(room_dates_path)

    # snapshots
    snapshots_dir = BASE / 'snapshots'
    snapshots = []
    for snap_path in snapshots_dir.glob('*.json'):
        snapshots.append(load_json(snap_path))
    out['snapshots'] = snapshots

    # aggregated pricing
    pricing_json_path = BASE / 'pricing' / 'pricing-dataset.json'
    pricing_csv_path = BASE / 'pricing' / 'pricing-dataset.csv'
    out['aggregated_pricing'] = {
        'json': load_json(pricing_json_path),
        'csv': load_csv_as_dicts(pricing_csv_path)
    }

    # raw pricing per village
    raw_base = BASE / 'pricing'
    villages = ['seydkola', 'gonehkola', 'quran_talar', 'shirdarkola', 'sample']
    out['raw_pricing'] = {}
    for v in villages:
        raw_dir = raw_base / f'{v}_raw'
        if raw_dir.is_dir():
            files = sorted(raw_dir.glob('*.json'))
            out['raw_pricing'][v] = [load_json(fp) for fp in files]
        else:
            out['raw_pricing'][v] = []

    # Write output
    output_path = Path('jajiga_complete_dataset.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'Aggregated dataset written to {output_path}')

if __name__ == '__main__':
    main()
```

**Step 2: Run script to produce output**
Run: `python scripts/aggregate_jajiga_dataset.py`
Expected: prints success message and creates `jajiga_complete_dataset.json`.

**Step 3: Verify output is valid JSON and contains all data**
We'll do a quick sanity check in the next task.

**Step 4: Commit**
```bash
git add scripts/aggregate_jajiga_dataset.py
git commit -m "feat: add dataset aggregation script"
```

---

### Task 4: Verify aggregation completeness

**Objective:** Ensure no data loss by checking that key fields from each source are present in the output.

**Files:** 
- Read: `jajiga_complete_dataset.json`
- Read: original sources for comparison

**Step 1: Write verification script**
```python
#!/usr/bin/env python3
"""
Verify that aggregated dataset contains all essential data from sources.
"""
import json
from pathlib import Path

BASE = Path('data')
AGG = Path('jajiga_complete_dataset.json')

def load_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def main():
    agg = load_json(AGG)
    errors = []
    warnings = []

    # Check hosts count
    hosts_path = BASE / 'hosts-babolkenar.json'
    hosts_data = load_json(hosts_path)
    expected_hosts = len(hosts_data.get('hosts', []))
    actual_hosts = len(agg.get('hosts', []))
    if expected_hosts != actual_hosts:
        errors.append(f'Hosts count mismatch: expected {expected_hosts}, got {actual_hosts}')
    else:
        print(f'✓ Hosts count: {actual_hosts}')

    # Check all-cabins meta
    all_cabins_path = BASE / 'all-cabins.json'
    all_cabins_data = load_json(all_cabins_path)
    if agg.get('all_cabins') != all_cabins_data:
        errors.append('all-cabins content mismatch')
    else:
        print('✓ all-cabins matches')

    # Check supply hosts count
    supply_path = BASE / 'supply-data.json'
    supply_data = load_json(supply_path)
    expected_supply_hosts = len(supply_data.get('hosts', []))
    actual_supply_hosts = len(agg.get('supply', {}).get('hosts', []))
    if expected_supply_hosts != actual_supply_hosts:
        errors.append(f'Supply hosts count mismatch: expected {expected_supply_hosts}, got {actual_supply_hosts}')
    else:
        print(f'✓ Supply hosts count: {actual_supply_hosts}')

    # Check supply rooms count
    expected_supply_rooms = len(supply_data.get('rooms', []))
    actual_supply_rooms = len(agg.get('supply', {}).get('rooms', []))
    if expected_supply_rooms != actual_supply_rooms:
        errors.append(f'Supply rooms count mismatch: expected {expected_supply_rooms}, got {actual_supply_rooms}')
    else:
        print(f'✓ Supply rooms count: {actual_supply_rooms}')

    # Check raw pricing counts per village
    for v in ['seydkola', 'gonehkola', 'quran_talar', 'shirdarkola', 'sample']:
        raw_dir = BASE / 'pricing' / f'{v}_raw'
        if raw_dir.is_dir():
            expected = len(list(raw_dir.glob('*.json')))
            actual = len(agg.get('raw_pricing', {}).get(v, []))
            if expected != actual:
                errors.append(f'Raw pricing {v} count mismatch: expected {expected}, got {actual}')
            else:
                print(f'✓ Raw pricing {v} count: {actual}')
        else:
            print(f'⚠ Raw pricing directory {v}_raw not found')

    # Check aggregated pricing json
    pricing_json_path = BASE / 'pricing' / 'pricing-dataset.json'
    if agg.get('aggregated_pricing', {}).get('json') != load_json(pricing_json_path):
        errors.append('Aggregated pricing JSON mismatch')
    else:
        print('✓ Aggregated pricing JSON matches')

    # Check aggregated pricing csv
    pricing_csv_path = BASE / 'pricing' / 'pricing-dataset.csv'
    import csv
    with open(pricing_csv_path, encoding='utf-8') as f:
        expected_csv = list(csv.DictReader(f))
    actual_csv = agg.get('aggregated_pricing', {}).get('csv', [])
    if expected_csv != actual_csv:
        errors.append('Aggregated pricing CSV mismatch')
    else:
        print('✓ Aggregated pricing CSV matches')

    # Check room-dates
    room_dates_path = BASE / 'supply' / 'room-dates.json'
    if agg.get('room_dates') != load_json(room_dates_path):
        errors.append('Room dates mismatch')
    else:
        print('✓ Room dates matches')

    # Check snapshots count
    snapshots_dir = BASE / 'snapshots'
    expected_snapshots = len(list(snapshots_dir.glob('*.json')))
    actual_snapshots = len(agg.get('snapshots', []))
    if expected_snapshots != actual_snapshots:
        errors.append(f'Snapshots count mismatch: expected {expected_snapshots}, got {actual_snapshots}')
    else:
        print(f'✓ Snapshots count: {actual_snapshots}')

    if errors:
        print('\\n❌ Errors found:')
        for e in errors:
            print(' -', e)
        raise SystemExit(1)
    else:
        print('\\n✅ All checks passed. No data loss detected.')

if __name__ == '__main__':
    main()
```

**Step 2: Run verification**
Run: `python scripts/verify_aggregation.py` (we'll create this script in the same step)
Expected: all checks passed.

**Step 3: If any errors, debug and fix aggregation script.**

**Step 4: Commit verification script and any fixes**
```bash
git add scripts/verify_aggregation.py
git commit -m "test: add verification script for dataset aggregation"
```
If fixes needed:
```bash
git add scripts/aggregate_jajiga_dataset.py
git commit -m "fix: adjust aggregation script to preserve all data"
```

---

### Task 5: Finalize and document output

**Objective:** Ensure the final output file is in the project root and add a brief README note.

**Files:** 
- Read: `jajiga_complete_dataset.json`
- Create/modify: `DATASET_README.md` (optional) or update existing README.

**Step 1: Confirm output file exists and is non-empty**
```bash
ls -lh jajiga_complete_dataset.json
head -5 jajiga_complete_dataset.json
tail -5 jajiga_complete_dataset.json
```

**Step 2: Add a note about the dataset in the project README (if exists) or create a simple note.**
We'll create a file `DATASET_INFO.md` with description.

```markdown
# Jajiga Tracker Complete Dataset

This file (`jajiga_complete_dataset.json`) contains a complete aggregation of all data collected in the jajiga-tracker project.

## Sources included
- `data/hosts-babolkenar.json` (hosts and their rooms)
- `data/all-cabins.json` (curated cabin list with occupancy stats)
- `data/supply-data.json` (supply timeline: hosts, rooms, months, village stats)
- `data/supply/room-dates.json` (per-room first photo/review dates)
- `data/snapshots/*.json` (historical snapshots of supply data)
- `data/pricing/pricing-dataset.json` and `.csv` (aggregated pricing data for 6 villages)
- Raw pricing JSON files for each village:
  - `data/pricing/seydkola_raw/*.json`
  - `data/pricing/gonehkola_raw/*.json`
  - `data/pricing/quran_talar_raw/*.json`
  - `data/pricing/shirdarkola_raw/*.json`
  - `data/pricing/sample_raw/*.json`

## Structure
See the top-level keys in the JSON: meta, hosts, hosts_meta, all_cabins, supply, room_dates, snapshots, aggregated_pricing, raw_pricing.

## Generated by
`scripts/aggregate_jajiga_dataset.py`
See `scripts/verify_aggregation.py` for validation.

## Notes
- All data is preserved as-is; no fields are removed or altered.
- Timestamps are in ISO 8601 UTC where applicable.
- The dataset is optimized for AI consumption: nested structures are kept minimal, lists are homogeneous.
```

**Step 3: Commit**
```bash
git add DATASET_INFO.md jajiga_complete_dataset.json
git commit -m "docs: add dataset info and commit final aggregated dataset"
```

---

### Summary

After completing these tasks, we will have:
- A single JSON file `jajiga_complete_dataset.json` in the project root containing all data.
- A verification script to ensure correctness.
- Documentation about the dataset.

**Plan ready.** Say "go" to start implementation, or tell me what to change.