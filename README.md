# Jev RAG Chinese Benchmark

Reproducible Chinese RAG reranking benchmark for [Jev](https://typesafe.ai) (TypeSafe System One), on the canonical Chinese reranking dataset [C-MTEB/T2Reranking](https://huggingface.co/datasets/C-MTEB/T2Reranking) (T2Ranking lineage, hard negatives included).

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.23322277-blue)](https://zenodo.org/record/23322277)

The frozen protocol lives in [PROTOCOL.md](PROTOCOL.md). Dataset mirror with all logs: [cnfeichen/jev-rag-zh-bench on HuggingFace](https://huggingface.co/datasets/cnfeichen/jev-rag-zh-bench). ModelScope mirror (China-friendly): [cnfeichen/jev-rag-zh-bench](https://modelscope.cn/datasets/cnfeichen/jev-rag-zh-bench). Design principles: staged and cost-capped (dry run $0.005, S1 $0.06, runtime breaker at $0.15), pinned model (`typesafe/jev-1.13-20260917`), single run per variant, full per-call JSONL logs published, limitations reported next to results.

```
uv run python scripts/prepare_data.py --n 100 --out s1   # seed 42, deterministic
uv run python scripts/run_bench.py --sample data/s1.jsonl --variant score-zh --max-cost-usd 0.15
uv run python scripts/run_bench.py --sample data/s1.jsonl --variant noul-zh  --max-cost-usd 0.15
uv run python scripts/analyze.py --sample data/s1.jsonl --logs s1.score-zh.jsonl s1.noul-zh.jsonl --tag s1
```

Companion artifacts: pattern library [awesome-jev-prompts](https://github.com/vicfei/awesome-jev-prompts) (51 patterns, CC0) and its orchestrator [jev-pipeline-skill](https://github.com/vicfei/jev-pipeline-skill). Independent community project; not affiliated with TypeSafe AI. MIT. 中文说明见下。

## 中文说明

面向 Jev（TypeSafe System One）的可复现中文 RAG 重排基准。数据：C-MTEB/T2Reranking（T2Ranking 系，含难负例）；模型锁定 `typesafe/jev-1.13-20260917`；阶梯式投入（干跑 $0.005 / S1 $0.06 / 运行时熔断 $0.15）；每次调用全量 JSONL 日志随仓库公开；单次运行、限制条款与结果同页发布。

## Jev 1.14 spot check (2026-10-19, first Chinese numbers)

`jev-latest` was found live-resolving to `typesafe/jev-1.14-20261014` (the docs page still said 1.13 — alias moved silently; anyone with unpinned thresholds is already on 1.14). We re-ran the full S1 score-zh protocol (100 queries, 1,000 calls, $0.037) on the pinned dated id:

| | nDCG@5 | vs BM25 (paired) | AUC | latency p50 |
|---|---:|---:|---:|---:|
| jev-1.13 (Oct 12) | 0.5461 | +0.133 [+0.051, +0.232] | 0.714 | 0.47s |
| **jev-1.14 (Oct 19)** | 0.5464 | +0.134 [+0.050, +0.231] | 0.711 | **0.66s** |

- **Quality: statistically unchanged.** Paired per-query nDCG@5 delta +0.0004 [95% CI −0.037, +0.038]; 92% of individual scores moved slightly (mean |Δ| 0.10 levels, only 1 pair ≥1 full level) — jitter, not a shift. Thresholds tuned on 1.13 do not need retuning for Chinese reranking.
- **The BM25 gain holds** on 1.14 with a nearly identical interval.
- **Latency: +40% at p50 (0.47→0.66s, same 8-worker protocol, same channel).** Single-day, single-channel measurement — treat as a flag to watch, not a verdict.

## S1 results (2026-10-12, n=100, single run)

Model pinned `typesafe/jev-1.13-20260917` via OpenRouter. Pools: 1 positive + 9 hard negatives each, passages ≤3,000 chars. Full logs in `logs/`.

| Ranker (Chinese) | nDCG@5 (95% CI) | nDCG@10 (95% CI) | MRR@10 | R@1 | R@5 |
|---|---:|---:|---:|---:|---:|
| **Jev Score (score-zh)** | **0.546** [0.481, 0.611] | **0.602** [0.553, 0.653] | **0.477** | **0.260** | 0.830 |
| Jev Noul (noul-zh) | 0.531 | 0.588 | 0.458 | 0.240 | **0.830** |
| BM25 (jieba) | 0.413 [0.353, 0.477] | 0.513 [0.475, 0.555] | 0.363 | 0.110 | 0.690 |

- **Paired delta (Jev Score − BM25): nDCG@5 +0.133 [95% CI +0.051, +0.232]; nDCG@10 +0.089 [+0.031, +0.157]** — bootstrap over queries (n=1000), intervals exclude zero.
- Jev Score beats BM25 by +13.3 nDCG@5 points on Chinese hard negatives; Recall@1 is 2.4×.
- Score vs Noul nearly tie (Δ0.015 nDCG@5): for pure ranking the binary question is enough — the rubric earns its keep only when you need levels.
- Separation AUC ≈ 0.715 for both primitives (hard negatives are genuinely hard: some negatives partially answer).
- Cost: **$0.071 for the whole S1** (2,000 calls, 1.68M input tokens). Latency p50 0.47s / p95 0.61s at 8 workers.
- Limitations: n=100, single run, binary relevance, one channel (OpenRouter), latency under concurrency. Threshold sweep for noul-zh in `results/`.

## S1 结果（中文）

锁定模型 `typesafe/jev-1.13-20260917`（OpenRouter 通道），100 查询 × (1 正例 + 9 难负例)。**Jev Score 在中文难负例上 nDCG@5 0.546，比 BM25 高 13.3 个点（配对差值 95% CI [+5.1, +23.2]，不含零），Recall@1 是其 2.4 倍**；Score 与 Noul 几乎打平（纯排序场景二值问题就够）；分离度 AUC≈0.715；全程成本 $0.071、p50 延迟 0.47s。限制条款见英文节。阈值扫描见 `results/s1_noul-zh_sweep.csv`。
