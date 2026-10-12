#!/usr/bin/env python3
"""Download T2Reranking dev, sample queries, build candidate pools.

Emits data/<name>.jsonl: {"qid", "query", "pool": [{"pid", "text", "relevant"}]}
plus an audit block printed to stdout. Deterministic under --seed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import urllib.request
from pathlib import Path

PARQUET_URL = ("https://huggingface.co/api/datasets/C-MTEB/T2Reranking/"
               "parquet/default/dev/0.parquet")
RAW = Path(__file__).resolve().parent.parent / "data" / "raw" / "t2reranking_dev.parquet"


def download() -> Path:
    if RAW.exists() and RAW.stat().st_size > 10_000_000:
        return RAW
    RAW.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {PARQUET_URL} …")
    req = urllib.request.Request(PARQUET_URL, headers={"User-Agent": "jev-rag-zh-benchmark/0.1"})
    part = RAW.with_suffix(".parquet.part")
    with urllib.request.urlopen(req, timeout=300) as r, open(part, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    part.rename(RAW)
    return RAW


def load_rows(path: Path) -> list[dict]:
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    return table.to_pylist()


def build(rows: list[dict], n_queries: int, seed: int, pool_negatives: int = 9,
          max_chars: int = 3000) -> list[dict]:
    rng = random.Random(seed)

    def ok(r):
        pool = [r["positive"][0]] + list(r["negative"][:pool_negatives])
        return (r.get("positive") and len(r.get("negative") or []) >= pool_negatives
                and all(len(t) <= max_chars for t in pool))

    qualified = [r for r in rows if ok(r)]
    print(f"qualified rows: {len(qualified)} / {len(rows)} "
          f"(>=1 positive, >= {pool_negatives} negatives, all texts <= {max_chars} chars)")
    picked = rng.sample(qualified, min(n_queries, len(qualified)))
    out = []
    for i, row in enumerate(picked):
        pos = row["positive"][0]
        negs = row["negative"][:pool_negatives]
        pool = [{"pid": f"{i:03d}-p", "text": pos, "relevant": True}] + [
            {"pid": f"{i:03d}-n{j}", "text": t, "relevant": False} for j, t in enumerate(negs)
        ]
        rng.shuffle(pool)
        out.append({"qid": f"q{i:03d}", "query": row["query"], "pool": pool})
    return out


def audit(sample: list[dict]) -> None:
    lens_q = [len(s["query"]) for s in sample]
    lens_p = [len(p["text"]) for s in sample for p in s["pool"]]
    pos_in_top5 = sum(
        1 for s in sample for p in s["pool"][:5] if p["relevant"]
    )
    print(f"queries: {len(sample)} | pool size: {len(sample[0]['pool'])}")
    print(f"query chars  p50≈{sorted(lens_q)[len(lens_q)//2]} max={max(lens_q)}")
    print(f"passage chars p50≈{sorted(lens_p)[len(lens_p)//2]} max={max(lens_p)} mean≈{sum(lens_p)//len(lens_p)}")
    print(f"positives landing in shuffled top-5 by chance check: {pos_in_top5} (expect ≈ n/2)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="s1")
    args = ap.parse_args()
    rows = load_rows(download())
    sample = build(rows, args.n, args.seed)
    audit(sample)
    out = RAW.parent.parent / f"{args.out}.jsonl"
    out.write_text(
        "\n".join(json.dumps(s, ensure_ascii=False) for s in sample) + "\n", encoding="utf-8"
    )
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
