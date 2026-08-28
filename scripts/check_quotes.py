# -*- coding: utf-8 -*-
"""Mechanical anti-hallucination check on tag files:
   1) every quote must be an exact substring of the corpus content
   2) themes must exist in taxonomy
   3) sentiment must be pos/neg/neutral
   Output: data/reviews_mining/quote_check.json + console summary."""
import glob
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "data/reviews_mining"
VALID_SENT = {"pos", "neg", "neutral"}


def read_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
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
    valid_themes = {t["id"] for t in tax["themes"]}

    checked, fake_quotes, bad_theme, bad_sent, missing = 0, [], set(), set(), 0
    for f in sorted(glob.glob(f"{BASE}/tags_shard_*.jsonl")):
        for t in read_jsonl(f):
            checked += 1
            key = f"{t['room_id']}:{t['review_id']}"
            c = corpus.get(key)
            if not c:
                missing += 1
                continue
            q = (t.get("quote") or "").strip()
            if q:
                if q not in (c.get("content") or ""):
                    fake_quotes.append({"shard_file": f, "key": key, "quote": q[:100]})
            for th in (t.get("themes") or []):
                if th not in valid_themes:
                    bad_theme.add(th)
            if (t.get("sentiment") or "neutral") not in VALID_SENT:
                bad_sent.add(t.get("sentiment"))

    report = {
        "checked": checked,
        "missing_in_corpus": missing,
        "fake_quotes_count": len(fake_quotes),
        "fake_quotes_sample": fake_quotes[:15],
        "invalid_themes": sorted(bad_theme),
        "invalid_sentiment": sorted(x for x in bad_sent if x),
        "pass": len(fake_quotes) == 0 and not bad_theme and not bad_sent and missing == 0,
    }
    json.dump(report, open(f"{BASE}/quote_check.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1)[:2000])


if __name__ == "__main__":
    main()
