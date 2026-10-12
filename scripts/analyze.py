#!/usr/bin/env python3
"""Compute metrics from run logs + sample; write results/<tag>_report.md + .csv."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def load(sample_path: str, logs: list[str]) -> list[dict]:
    sample = {s["qid"]: s for s in map(json.loads, Path(sample_path).read_text().splitlines())}
    rows = []
    for lp in logs:
        for line in Path(lp).read_text().splitlines():
            r = json.loads(line)
            if r["status"] != 200:
                continue
            rows.append(r)
    return rows, sample


def score_of(rec: dict) -> float | None:
    ans = (rec.get("answer") or {}).get(list((rec.get("answer") or {}).keys())[0] if rec.get("answer") else "", {})
    if not ans:
        return None
    if ans.get("type") == "score":
        return float(ans.get("score", 0))
    if ans.get("type") == "noul":
        return float(ans.get("noul", 0))
    return None


def qkey(rec):
    return (rec["qid"], rec["variant"])


def ndcg(ranking: list[bool], k: int) -> float:
    dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ranking[:k]))
    idcg = 1.0 / math.log2(2)  # single positive
    return dcg / idcg


def per_query(rows: list[dict], sample: dict, variant: str) -> dict[str, dict]:
    """Per-query metric values; the unit of bootstrap resampling."""
    by_q = {}
    for r in rows:
        if r["variant"] == variant:
            by_q.setdefault(r["qid"], {})[r["pid"]] = score_of(r)
    out = {}
    for qid, scores in by_q.items():
        pool = sample[qid]["pool"]
        order = sorted(pool, key=lambda p: -(scores.get(p["pid"]) if scores.get(p["pid"]) is not None else -1))
        rels = [p["relevant"] for p in order]
        rank = next((i + 1 for i, p in enumerate(order) if p["relevant"]), 99)
        out[qid] = {
            "nDCG@5": ndcg(rels, 5), "nDCG@10": ndcg(rels, 10),
            "MRR@10": 1.0 / rank if rank <= 10 else 0.0,
            "R@1": float(rank <= 1), "R@3": float(rank <= 3), "R@5": float(rank <= 5),
        }
    return out


def bootstrap_ci(values: dict[str, float], n_boot: int = 1000, seed: int = 42) -> tuple[float, float]:
    """95% CI of the mean, resampling queries with replacement."""
    import random

    rng = random.Random(seed)
    keys = sorted(values)
    means = []
    for _ in range(n_boot):
        picked = rng.choices(keys, k=len(keys))
        vals = [values[k] for k in picked]
        means.append(sum(vals) / len(vals))
    means.sort()
    return means[int(0.025 * n_boot)], means[int(0.975 * n_boot)]


def metrics(rows: list[dict], sample: dict, variant: str) -> dict:
    pq = per_query(rows, sample, variant)
    if not pq:
        return {"n": 0}
    out = {"n": len(pq)}
    for m in ("nDCG@5", "nDCG@10", "MRR@10", "R@1", "R@3", "R@5"):
        vals = {q: v[m] for q, v in pq.items()}
        lo, hi = bootstrap_ci(vals)
        mean = sum(vals.values()) / len(vals)
        out[m] = mean
        out[f"{m}_ci"] = (lo, hi)
    return out


def separation(rows: list[dict], variant: str) -> dict:
    pos, neg = [], []
    for r in rows:
        if r["variant"] != variant:
            continue
        v = score_of(r)
        if v is None:
            continue
        (pos if r["pid"].endswith("-p") else neg).append(v)
    if not pos or not neg:
        return {}
    auc = sum((1 if p > ng else 0.5 if p == ng else 0) for p in pos for ng in neg) / (len(pos) * len(neg))
    return {"mean_pos": sum(pos) / len(pos), "mean_neg": sum(neg) / len(neg),
            "AUC": auc, "n_pos": len(pos), "n_neg": len(neg)}


def threshold_sweep(rows: list[dict], variant: str) -> list[tuple]:
    out = []
    for cut in [i / 20 for i in range(1, 20)]:
        tp = fp = fn = tn = 0
        for r in rows:
            if r["variant"] != variant:
                continue
            v = score_of(r)
            if v is None:
                continue
            pos = r["pid"].endswith("-p")
            pred = v >= cut
            tp += pos and pred; fp += (not pos) and pred
            fn += pos and not pred; tn += (not pos) and not pred
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        out.append((cut, prec, rec))
    return out


def bm25_per_query(sample: dict) -> dict[str, dict]:
    import jieba
    from rank_bm25 import BM25Okapi

    out = {}
    for qid, s in sample.items():
        toks = lambda t: list(jieba.cut_for_search(t))
        bm = BM25Okapi([toks(p["text"]) for p in s["pool"]])
        scores = bm.get_scores(toks(s["query"]))
        order = sorted(zip(s["pool"], scores), key=lambda x: -x[1])
        rank = next((i + 1 for i, (p, _) in enumerate(order) if p["relevant"]), 99)
        rels = [p["relevant"] for p, _ in order]
        out[qid] = {
            "nDCG@5": ndcg(rels, 5), "nDCG@10": ndcg(rels, 10),
            "MRR@10": 1.0 / rank if rank <= 10 else 0.0,
            "R@1": float(rank <= 1), "R@3": float(rank <= 3), "R@5": float(rank <= 5),
        }
    return out


def bm25_baseline(sample: dict) -> dict:
    pq = bm25_per_query(sample)
    out = {"n": len(pq)}
    for m in ("nDCG@5", "nDCG@10", "MRR@10", "R@1", "R@3", "R@5"):
        vals = {q: v[m] for q, v in pq.items()}
        lo, hi = bootstrap_ci(vals)
        out[m] = sum(vals.values()) / len(vals)
        out[f"{m}_ci"] = (lo, hi)
    return out


def paired_delta(a: dict[str, dict], b: dict[str, dict], metric: str,
                 n_boot: int = 1000, seed: int = 42) -> tuple[float, float, float]:
    """Paired mean difference a-b on shared qids, with bootstrap CI."""
    import random

    rng = random.Random(seed)
    shared = sorted(set(a) & set(b))
    diffs = {q: a[q][metric] - b[q][metric] for q in shared}
    mean = sum(diffs.values()) / len(diffs)
    means = []
    for _ in range(n_boot):
        picked = rng.choices(shared, k=len(shared))
        vals = [diffs[q] for q in picked]
        means.append(sum(vals) / len(vals))
    means.sort()
    return mean, means[int(0.025 * n_boot)], means[int(0.975 * n_boot)]


def fmt(m: dict) -> str:
    if m.get("n", 0) == 0:
        return "n/a"
    parts = [f"n={m['n']}"]
    for k, v in m.items():
        if k == "n" or k.endswith("_ci"):
            continue
        ci = m.get(f"{k}_ci")
        parts.append(f"{k}={v:.4f}" + (f" [{ci[0]:.4f},{ci[1]:.4f}]" if ci else ""))
    return " | ".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", required=True)
    ap.add_argument("--logs", nargs="+", required=True)
    ap.add_argument("--tag", default="s1")
    args = ap.parse_args()
    rows, sample = load(args.sample, args.logs)
    lat = sorted(r["latency_s"] for r in rows)
    spent = sum(float((r.get("usage") or {}).get("cost") or 0) for r in rows)
    tokens = sum(int((r.get("usage") or {}).get("input_tokens") or 0) for r in rows)

    lines = [f"# {args.tag} results", ""]
    for v in sorted({r["variant"] for r in rows}):
        lines += [f"## {v}", "- ranking: " + fmt(metrics(rows, sample, v)), ""]
        sep = separation(rows, v)
        if sep:
            mp, mn, auc = sep["mean_pos"], sep["mean_neg"], sep["AUC"]
            nn = str(sep["n_pos"]) + "+" + str(sep["n_neg"])
            lines += [f"- separation: mean_pos={mp:.3f} mean_neg={mn:.3f} AUC={auc:.3f} (n={nn})", ""]
    lines += [f"- BM25 baseline: {fmt(bm25_baseline(sample))}", ""]
    best_variant = max(
        (v for v in {r["variant"] for r in rows}),
        key=lambda v: metrics(rows, sample, v).get("nDCG@5", 0), default=None,
    )
    if best_variant:
        pq_best = per_query(rows, sample, best_variant)
        pq_bm = bm25_per_query(sample)
        for metric_name in ("nDCG@5", "nDCG@10"):
            mean, lo, hi = paired_delta(pq_best, pq_bm, metric_name)
            lines += [f"- paired delta ({best_variant} − BM25), {metric_name}: "
                      f"{mean:+.4f} [{lo:+.4f},{hi:+.4f}] (95% bootstrap, n=1000)"]
    lines += ["", f"- calls: {len(rows)} | input tokens: {tokens:,} | cost: ${spent:.4f}",
              f"- latency p50={lat[len(lat)//2]:.2f}s p95={lat[int(len(lat)*0.95)]:.2f}s (8 workers)"]
    report = Path(f"results/{args.tag}_report.md")
    report.parent.mkdir(exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    # threshold sweep CSV for the noul variant
    for v in ("noul-zh",):
        if any(r["variant"] == v for r in rows):
            csv = Path(f"results/{args.tag}_{v}_sweep.csv")
            csv.write_text("cutoff,precision,recall\n" + "\n".join(
                f"{c:.2f},{p:.4f},{r:.4f}" for c, p, r in threshold_sweep(rows, v)) + "\n")
            print(f"wrote {csv}")


if __name__ == "__main__":
    main()
