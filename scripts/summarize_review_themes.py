# -*- coding: utf-8 -*-
"""Aggregate theme tags into stats for report + HTML dashboard.

Inputs:  data/reviews_mining/corpus.json + data/reviews_mining/tags_shard_*.json
Output:  data/reviews_mining/theme_stats.json
"""
import glob
import json
import os
import sys
import io
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "data/reviews_mining"


def read_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # tolerate a wrapped array line or stray brackets
            if line.startswith("[") and line.endswith("]"):
                out.extend(json.loads(line))
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def main():
    corpus = {f"{r['room_id']}:{r['review_id']}": r
              for r in json.load(open(f"{BASE}/corpus.json", encoding="utf-8"))}
    tax = json.load(open(f"{BASE}/taxonomy.json", encoding="utf-8"))
    theme_fa = {t["id"]: t["fa"] for t in tax["themes"]}

    tags, missing = [], 0
    for f in sorted(glob.glob(f"{BASE}/tags_shard_*.jsonl")):
        for t in read_jsonl(f):
            key = f"{t['room_id']}:{t['review_id']}"
            if key in corpus:
                tags.append(t)
            else:
                missing += 1
    print(f"tags loaded: {len(tags)} | not in corpus (skipped): {missing}")

    # --- global theme stats
    theme_count = Counter()
    theme_sent = defaultdict(Counter)   # theme -> pos/neg/neutral
    theme_prov = defaultdict(Counter)   # theme -> province
    theme_year = defaultdict(Counter)   # theme -> year
    sentiment_total = Counter()
    tagged_keys = set()

    for t in tags:
        key = f"{t['room_id']}:{t['review_id']}"
        tagged_keys.add(key)
        c = corpus[key]
        sentiment_total[t.get("sentiment") or "neutral"] += 1
        for th in (t.get("themes") or [])[:2]:
            theme_count[th] += 1
            theme_sent[th][t.get("sentiment") or "neutral"] += 1
            theme_prov[th][c.get("province") or "?"] += 1
            theme_year[th][(c.get("created_at") or "????")[:4]] += 1

    # --- top negative quotes per theme (longest useful, with room title)
    quotes = defaultdict(list)
    for t in tags:
        q = (t.get("quote") or "").strip()
        if not q or t.get("sentiment") != "neg":
            continue
        key = f"{t['room_id']}:{t['review_id']}"
        c = corpus[key]
        for th in (t.get("themes") or [])[:2]:
            quotes[th].append({"q": q, "room": c.get("title"), "rating": c.get("rating"),
                               "date": c.get("created_at")})
    top_quotes = {}
    for th, qs in quotes.items():
        # dedupe by q text, prefer 90-140 char quotes
        seen, picked = set(), []
        for x in sorted(qs, key=lambda x: -min(len(x["q"]), 140)):
            if x["q"] in seen:
                continue
            seen.add(x["q"])
            picked.append(x)
            if len(picked) >= 6:
                break
        top_quotes[th] = picked

    # --- ratings of tagged reviews vs all
    rated = [c.get("rating") for c in corpus.values() if isinstance(c.get("rating"), (int, float))]
    avg_rating_all = round(sum(rated) / len(rated), 3) if rated else None

    stats = {
        "generated_from": {"corpus_reviews": len(corpus), "tagged_reviews": len(tagged_keys)},
        "sentiment_total": dict(sentiment_total),
        "avg_rating_all": avg_rating_all,
        "themes": [
            {
                "id": th,
                "fa": theme_fa.get(th, th),
                "count": theme_count[th],
                "pos": theme_sent[th]["pos"],
                "neg": theme_sent[th]["neg"],
                "neutral": theme_sent[th]["neutral"],
                "by_province": dict(theme_prov[th].most_common()),
                "by_year": dict(sorted(theme_year[th].items())),
                "quotes_neg": top_quotes.get(th, []),
            }
            for th, _ in theme_count.most_common()
        ],
        "coverage": {
            "tagged_pct": round(100 * len(tagged_keys) / max(1, len(corpus)), 1),
            "reviews_missing_tags": len(corpus) - len(tagged_keys),
        },
    }
    json.dump(stats, open(f"{BASE}/theme_stats.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"avg rating (all corpus): {avg_rating_all}")
    print("theme ranking:")
    for t in stats["themes"]:
        print(f"  {t['fa']}: {t['count']} (neg={t['neg']}, pos={t['pos']})")
    print(f"coverage: {stats['coverage']}")
    print("saved theme_stats.json")


if __name__ == "__main__":
    main()
