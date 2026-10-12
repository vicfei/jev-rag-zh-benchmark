"""Offline tests: metric math and pool construction — no network, no key."""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from analyze import ndcg  # noqa: E402
from prepare_data import build  # noqa: E402


def test_ndcg_perfect_and_worst():
    assert ndcg([True] + [False] * 9, 5) == 1.0
    # positive at rank 10: dcg = 1/log2(11)
    assert math.isclose(ndcg([False] * 9 + [True], 10), 1 / math.log2(11))
    # positive beyond cutoff → 0
    assert ndcg([False] * 5 + [True], 5) == 0.0


def test_build_pool_invariants():
    rows = [
        {"query": f"q{i}", "positive": [f"pos{i}"], "negative": [f"neg{i}_{j}" for j in range(12)]}
        for i in range(50)
    ]
    s1 = build(rows, n_queries=10, seed=42)
    s2 = build(rows, n_queries=10, seed=42)
    assert len(s1) == 10
    # deterministic under the same seed
    assert [x["qid"] for x in s1] == [x["qid"] for x in s2]
    for s in s1:
        assert len(s["pool"]) == 10
        assert sum(p["relevant"] for p in s["pool"]) == 1
        assert s["pool"][0]["text"].startswith(("pos", "neg"))  # verbatim passthrough


def test_qualification_filter():
    rows = [
        {"query": "ok", "positive": ["p"], "negative": [f"n{i}" for i in range(9)]},   # qualifies
        {"query": "few", "positive": ["p"], "negative": ["n1", "n2"]},                # too few negs
        {"query": "nopos", "positive": [], "negative": [f"n{i}" for i in range(20)]}, # no positive
    ]
    s = build(rows, n_queries=5, seed=1)
    assert len(s) == 1 and s[0]["query"] == "ok"


def test_bootstrap_ci_collapses_on_constants():
    from analyze import bootstrap_ci
    vals = {f"q{i}": 0.5 for i in range(50)}
    lo, hi = bootstrap_ci(vals, n_boot=200)
    assert lo == hi == 0.5


def test_paired_delta_sign():
    from analyze import paired_delta
    a = {"q1": {"nDCG@5": 0.8}, "q2": {"nDCG@5": 0.6}}
    b = {"q1": {"nDCG@5": 0.4}, "q2": {"nDCG@5": 0.5}}
    mean, lo, hi = paired_delta(a, b, "nDCG@5", n_boot=100)
    assert mean > 0 and lo <= mean <= hi
