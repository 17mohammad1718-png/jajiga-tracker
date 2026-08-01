"""Merge per-village pricing files into the combined pricing-dataset.json.

Reads all data/pricing/{slug}-pricing.json and merges into pricing-dataset.json
(sorted by village then price) + regenerates pricing-dataset.csv.
"""
import json, os, csv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICING_DIR = os.path.join(ROOT, "data", "pricing")
OUT_JSON = os.path.join(PRICING_DIR, "pricing-dataset.json")
OUT_CSV = os.path.join(PRICING_DIR, "pricing-dataset.csv")

VILLAGE_SLUGS = {
    "سیدکلا": "seydkola",
    "گونه کلا": "gonehkola",
    "قرآن تالار": "quran_talar",
    "شیردارکلا": "shirdarkola",
}

def main():
    all_data = []
    for village, slug in VILLAGE_SLUGS.items():
        path = os.path.join(PRICING_DIR, f"{slug}-pricing.json")
        if not os.path.exists(path):
            print(f"SKIP (missing): {path}")
            continue
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
        for r in items:
            r["village"] = village
            r["village_slug"] = slug
        all_data.extend(items)
        print(f"{village}: {len(items)}")

    all_data.sort(key=lambda r: (r.get("village", ""), r.get("min_price") is None, r.get("min_price") or 0))
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=1)
    print(f"\nCombined: {len(all_data)} -> {OUT_JSON}")

    if all_data:
        flat_keys = [k for k in all_data[0].keys() if k not in ("features", "feature_desc", "discounts", "types", "regions", "properties", "geo")]
        with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=flat_keys + ["features", "properties", "geo_lat", "geo_lng", "discounts"])
            w.writeheader()
            for r in all_data:
                row = {k: r.get(k) for k in flat_keys}
                row["features"] = "|".join(r.get("features") or [])
                row["properties"] = "|".join(r.get("properties") or [])
                geo = r.get("geo") or {}
                row["geo_lat"] = geo.get("lat")
                row["geo_lng"] = geo.get("lng")
                row["discounts"] = json.dumps(r.get("discounts") or [], ensure_ascii=False)
                w.writerow(row)
        print(f"CSV saved: {OUT_CSV}")

if __name__ == "__main__":
    main()
