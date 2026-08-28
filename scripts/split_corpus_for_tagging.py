# -*- coding: utf-8 -*-
"""Stratified sampler: pick ~N reviews for LLM tagging, stratified by
province x keyword-sentiment (strata from keyword_tags.json).
Output: data/reviews_mining/tag_input_shard_{i}.json (i = 0..S-1), S shards for S agents."""
import json
import random
import sys
import io
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "data/reviews_mining"
SAMPLE_N = 6000
SHARDS = 5
SEED = 42


def main():
    sample_n = int(sys.argv[1]) if len(sys.argv) > 1 else SAMPLE_N
    random.seed(SEED)
    corpus = {f"{r['room_id']}:{r['review_id']}": r
              for r in json.load(open(f"{BASE}/corpus.json", encoding="utf-8"))}
    kw = json.load(open(f"{BASE}/keyword_tags.json", encoding="utf-8"))

    strata = defaultdict(list)
    for key, t in kw.items():
        c = corpus.get(key)
        if not c or not (c.get("content") or "").strip():
            continue
        prov = c.get("province") or "?"
        sent = t.get("kw_sentiment") or "neutral"
        strata[(prov, sent)].append(key)

    total_eligible = sum(len(v) for v in strata.values())
    picked = []
    for stratum, keys in sorted(strata.items()):
        n = max(20, round(sample_n * len(keys) / total_eligible))
        n = min(n, len(keys))
        picked.extend(random.sample(keys, n))
    # trim to sample_n if strata minimums pushed us over
    if len(picked) > sample_n:
        picked = random.sample(picked, sample_n)
    random.shuffle(picked)
    print(f"eligible: {total_eligible} | sampled: {len(picked)} | strata: {len(strata)}")

    shards = [[] for _ in range(SHARDS)]
    for i, key in enumerate(picked):
        c = corpus[key]
        shards[i % SHARDS].append({
            "review_id": c["review_id"],
            "room_id": c["room_id"],
            "content": c["content"],
            "rating": c.get("rating"),
            "created_at": c.get("created_at"),
        })
    for i, s in enumerate(shards):
        # JSONL: one review per line so agents can read_file with offset/limit pagination
        with open(f"{BASE}/tag_input_shard_{i}.jsonl", "w", encoding="utf-8") as f:
            for r in s:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"tag_input_shard_{i}.jsonl: {len(s)} reviews")


if __name__ == "__main__":
    main()
