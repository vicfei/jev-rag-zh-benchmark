# Protocol — jev-rag-zh-benchmark (v1.1, frozen 2026-10-08)

Reproducible Chinese RAG reranking benchmark for Jev. Everything that affects a
number is written here; the scripts implement exactly this and nothing more.

## Data

- **Dataset**: [C-MTEB/T2Reranking](https://huggingface.co/datasets/C-MTEB/T2Reranking), `dev` split (6,129 rows).
  Each row: `query`, `positive[]`, `negative[]`. Canonical Chinese reranking task
  (T2Ranking lineage, C-MTEB leaderboard member), with **hard negatives**.
- **Selection note**: the originally planned C-MTEB/T2Retrieval exposes only
  corpus+queries on HF (no qrels), so graded pools are not constructible from the
  public artifact; T2Reranking gives canonical pools directly. Trade-off: binary
  relevance instead of graded.
- **Sampling**: seed 42. S1 = 100 queries, dry run = 20. A row qualifies if it has
  ≥1 positive and ≥9 negatives. Pool = first positive + first 9 negatives
  (dataset order), positive position shuffled within the pool (seeded).
  Passages are used verbatim (HTML artifacts included) — fidelity over aesthetics.

## Model & channel

- Channel: OpenRouter `POST https://openrouter.ai/api/v1/systemone`
  (measured 2026-10-08: same endpoint path as TypeSafe direct; billed at
  $0.042/M input, output free).
- Model: **`typesafe/jev-1.13-20260917`**, pinned. The dated ID is OpenRouter's
  namespace form; TypeSafe-direct uses `jev-1.13.0`. Version ids are not
  interchangeable across channels — recorded here as a finding.
- The `model` field of every response is logged; any drift aborts the run.

## Question variants (S1)

One request per (query, passage). State is `{"query": ..., "passage": ...}`;
question text is frozen byte-exact (SHA256 logged):

- **score-zh** — `Score`, instructions `"该段落对回答该查询有多大帮助？"`, criteria:
  `["不相关：与查询主题无关或未回答查询。", "相关但不回答：主题相关，但未回答查询。",
  "部分回答：包含查询答案的一部分。", "直接回答：完整回答该查询。"]`
- **noul-zh** — `Noul`, instructions `"仅凭该段落能回答该查询吗？"`

(S2 will add English-wording variants + consistency rerun + an LLM-judge
subset; not part of this frozen protocol version.)

## Metrics

- Ranking: nDCG@5, nDCG@10 (binary gains), MRR@10, Recall@1/3/5
  (position of the single positive).
- Separation: mean score positive vs negative; rank-AUC of score/noul
  separating positive from hard negatives.
- Threshold sweep (noul): precision/recall per 0.05 cutoff for
  "passage answers the query".
- Baselines: pool position before shuffle is dataset order — reported as
  *pool floor* only if informative; **BM25** (jieba tokens, rank_bm25) is the
  real anchor.
- Latency: p50/p95 over the S1 calls (concurrency noted; rate-limit noise
  acknowledged).

## Cost discipline

- Dry run budget $0.01; S1 budget $0.15 hard cap (`--max-cost-usd`).
- Pre-run balance check: refuse to start if balance < 2× stage budget.
- 8 concurrent workers max (community norm for probe loops).
- Every call's `usage` is logged; the report's cost table must reconcile with
  the sum of logged usage.

## Honesty clauses

- Single run per variant; no seed shopping; full per-call JSONL logs published.
- Limitations reported alongside results: n=100, single run, binary relevance,
  OpenRouter channel (not TypeSafe-direct), latency measured under concurrency.
- Negative or null results are published as-is.
