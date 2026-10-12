# Jev RAG Chinese Benchmark

Reproducible Chinese RAG reranking benchmark for [Jev](https://typesafe.ai) (TypeSafe System One), on the canonical Chinese reranking dataset [C-MTEB/T2Reranking](https://huggingface.co/datasets/C-MTEB/T2Reranking) (T2Ranking lineage, hard negatives included).

The frozen protocol lives in [PROTOCOL.md](PROTOCOL.md). Design principles: staged and cost-capped (dry run $0.005, S1 $0.06, runtime breaker at $0.15), pinned model (`typesafe/jev-1.13-20260917`), single run per variant, full per-call JSONL logs published, limitations reported next to results.

```
uv run python scripts/prepare_data.py --n 100 --out s1   # seed 42, deterministic
uv run python scripts/run_bench.py --sample data/s1.jsonl --variant score-zh --max-cost-usd 0.15
uv run python scripts/run_bench.py --sample data/s1.jsonl --variant noul-zh  --max-cost-usd 0.15
uv run python scripts/analyze.py --sample data/s1.jsonl --logs s1.score-zh.jsonl s1.noul-zh.jsonl --tag s1
```

Companion artifacts: pattern library [awesome-jev-prompts](https://github.com/vicfei/awesome-jev-prompts) (51 patterns, CC0) and its orchestrator [jev-pipeline-skill](https://github.com/vicfei/jev-pipeline-skill). Independent community project; not affiliated with TypeSafe AI. MIT. 中文说明见下。

## 中文说明

面向 Jev（TypeSafe System One）的可复现中文 RAG 重排基准。数据：C-MTEB/T2Reranking（T2Ranking 系，含难负例）；模型锁定 `typesafe/jev-1.13-20260917`；阶梯式投入（干跑 $0.005 / S1 $0.06 / 运行时熔断 $0.15）；每次调用全量 JSONL 日志随仓库公开；单次运行、限制条款与结果同页发布。
