# -*- coding: utf-8 -*-
"""Merge micro-chunk part files (tags_shard_N{a,b}_p*.jsonl) into tags_shard_N.jsonl
for shards 0-2 (3 and 4 already final). Dedupes by review_id, reports counts."""
import glob
import json
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "data/reviews_mining"


def main():
    grand = 0
    for i in range(3):
        parts = sorted(glob.glob(f"{BASE}/tags_shard_{i}a_p*.jsonl")) + \
                sorted(glob.glob(f"{BASE}/tags_shard_{i}b_p*.jsonl"))
        seen = {}
        for p in parts:
            for line in open(p, encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                # tolerate wrapped-array part files
                if line.startswith("["):
                    try:
                        items = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    for it in items if isinstance(items, list) else []:
                        seen[str(it.get("review_id"))] = line if isinstance(it, dict) else json.dumps(it, ensure_ascii=False)
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, list):
                    for it in obj:
                        seen[str(it.get("review_id"))] = json.dumps(it, ensure_ascii=False)
                else:
                    seen[str(obj.get("review_id"))] = line
        out = f"{BASE}/tags_shard_{i}.jsonl"
        with open(out, "w", encoding="utf-8") as f:
            for line in seen.values():
                f.write(line + "\n")
        print(f"shard {i}: parts={len(parts)} unique_lines={len(seen)} -> {out}")
        grand += len(seen)
    print(f"grand total (shards 0-2): {grand} | +shards 3,4 = {grand + 2400} / 6000")


if __name__ == "__main__":
    main()
