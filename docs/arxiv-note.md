# Technical note draft (for arXiv cs.IR submission)

> Status: draft for endorsement + submission. Numbers frozen from S1 logs
> (2026-10-12, `logs/` in this repo). LaTeX conversion at submission time.

---

**Title:** Jev as a Chinese RAG Reranker: A Reproducible First Measurement
**Authors:** Fei Chen (independent; vicfei on GitHub)

## Abstract

Jev, the first publicly available "System One" model (TypeSafe AI), returns typed
answers — Choice, Score, Noul — with calibrated probabilities instead of text,
at a listed input price of \$0.042/M tokens. Community adoption has concentrated
in English- and Turkish-language reranking evaluations; no Chinese-language
measurements exist, and threshold transferability across languages is an open
question. We present a reproducible benchmark of Jev as a reranker over hard
negatives from the canonical Chinese reranking dataset T2Reranking (T2Ranking
lineage; C-MTEB member): 100 queries, each with one positive and nine hard
negative passages, model version pinned, every API call logged. Jev's Score
primitive outperforms a BM25 baseline by +0.133 nDCG@5 (95% bootstrap CI
[+0.051, +0.232]; paired per-query deltas, intervals excluding zero) and 2.4×
Recall@1, at a total API cost of \$0.07 for the full run. The Score (4-level
rubric) and Noul (binary) question forms produce statistically
indistinguishable ranking quality, suggesting the binary form suffices for
ranking and the rubric earns its keep only when graded output is required.
We release the protocol, scripts, per-call logs, and threshold sweeps.

## 1. Introduction

Retrieval-augmented generation pipelines spend a large fraction of their budget
on a decision that is not generative at all: which retrieved passages enter the
prompt. Jev [1] positions typed decision models for exactly this class of work.
English-language evaluations exist for LlamaIndex-style reranking [2] and a
Turkish-language reproducible benchmark [3] reports Cohere leading Jev on
ordering quality at 60.6% higher cost; but the Chinese setting — a major RAG
deployment language — has no published measurements, and a Japanese replication
already suggests calibrated thresholds do not transfer across languages [4].

This note contributes: (a) the first reproducible Chinese-language Jev reranking
measurement, over hard negatives rather than random negatives; (b) a
cost-disciplined protocol (staged budgets, pinned model, full call logs) that
others can extend; (c) a comparison of question forms (rubric vs binary) on
ranking quality.

## 2. Protocol

**Data.** C-MTEB/T2Reranking dev [5]: rows of (query, positive[], negative[]).
We qualify rows with ≥1 positive, ≥9 negatives, and all pool texts ≤3,000
characters (the character cap excludes a long tail up to 120k chars that would
exceed the model's 32k-token state budget; 1,839/6,129 rows qualify). S1 sample:
100 queries, seed 42; pool = first positive + first 9 negatives (dataset
order), positive position shuffled (seeded). Passages verbatim.

**Model.** `typesafe/jev-1.13-20260917` via OpenRouter's `/v1/systemone`
endpoint (pinned dated id; the alias `jev-latest` is unpinned by design and the
TypeSafe-direct id format `jev-1.13.0` is not interchangeable across channels —
recorded as a finding). Each response's returned model id is logged and
verified constant.

**Questions.** One request per (query, passage); state = {query, passage}.
Two frozen Chinese question forms: score-zh (Score, 4-level relevance rubric)
and noul-zh (Noul, "does this passage alone answer the query"). Question text
SHA256-logged.

**Baselines and metrics.** BM25 (jieba tokenization, Okapi) as the anchor;
pool-position floor reported in logs. nDCG@5/@10 (binary gains, single positive
per pool), MRR@10, Recall@1/3/5. Bootstrap 95% CIs (1,000 resamples, queries as
units) for means and for paired per-query deltas against BM25.

**Cost discipline.** Runtime circuit breaker (\$0.15), pre-run balance check,
8-worker cap, per-call usage logged. Total S1 spend: \$0.071 (2,000 calls,
1.68M input tokens).

## 3. Results

| Ranker | nDCG@5 (95% CI) | nDCG@10 (95% CI) | MRR@10 | R@1 | R@5 |
|---|---:|---:|---:|---:|---:|
| Jev Score (score-zh) | **0.546** [0.481, 0.611] | **0.602** [0.553, 0.653] | **0.477** | **0.260** | 0.830 |
| Jev Noul (noul-zh) | 0.531 | 0.588 | 0.458 | 0.240 | **0.830** |
| BM25 (jieba) | 0.413 [0.353, 0.477] | 0.513 [0.475, 0.555] | 0.363 | 0.110 | 0.690 |

Paired deltas (Jev Score − BM25): nDCG@5 **+0.133 [+0.051, +0.232]**;
nDCG@10 **+0.089 [+0.031, +0.157]** — both intervals exclude zero.

Separation on hard negatives: AUC 0.714 (Score) / 0.718 (Noul). Some hard
negatives partially answer the query (score ≥2.9 in 4% of cases), and 5% of
positives score below 1.0 — hard negatives are genuinely hard, and these
per-call logs are released as material for question-design research [6].
Latency p50 0.47s / p95 0.61s at 8 workers.

## 4. Discussion

Three observations. (1) The rubric does not buy ranking quality over the
binary form (Δ0.015 nDCG@5, within CI overlap): for pure ranking, the cheaper
question suffices; graded output matters when downstream logic consumes levels.
(2) The gain over BM25 concentrates in Recall@1 (2.4×), consistent with Jev
reading "does this answer the question" where lexical overlap fails. (3) At
\$0.0000375 per (query, passage) call, full-pool scoring costs ~\$0.0004 per
query — reranking by typed decision is economically negligible next to the
generation it feeds.

## 5. Limitations

n=100 queries; single run per variant (no consistency rerun in S1); binary
relevance (T2Reranking provides positives/hard negatives, not graded labels);
one channel (OpenRouter; TypeSafe-direct cross-check pending); latency
measured under concurrency; the character cap (≤3,000) excludes long-document
regimes. S2 (in preparation) extends to 300 queries, English-wording variants,
a consistency rerun, and an LLM-judge subset.

## 6. Reproducibility

Seed-fixed sampling, frozen question text (SHA256-logged), pinned model id
verified per call, per-call JSONL logs, cost reconciliation against logged
usage, and all scripts are in the repository. Everything in this note can be
re-derived by running the three scripts in order.

## References

[1] TypeSafe AI. Introducing System One Models & Jev. https://typesafe.ai/blog/introducing-system-one-models-and-jev (2026).
[2] WiktorB2004. llama-index-jev: LlamaIndex adapter with JevRerank. https://github.com/WiktorB2004/llama-index-jev (2026).
[3] erendikmenn. jev-rag-benchmark: reproducible Turkish-language Jev reranking benchmark. https://github.com/erendikmenn/jev-rag-benchmark (2026).
[4] Community reports of Japanese-language threshold non-transfer. Collected in awesome-jev-prompts ecosystem notes. https://github.com/vicfei/awesome-jev-prompts (2026).
[5] Tang, X., et al. T2Ranking: A large-scale Chinese Benchmark for Passage Ranking. SIGIR 2023. Dataset: C-MTEB/T2Reranking. https://huggingface.co/datasets/C-MTEB/T2Reranking
[6] vicfei. awesome-jev-prompts: question patterns, anti-patterns & calibration notes for Jev. https://github.com/vicfei/awesome-jev-prompts (2026).
