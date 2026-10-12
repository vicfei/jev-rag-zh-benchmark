# dry results

## score-zh
- ranking: n=20 | nDCG@5=0.5286 | nDCG@10=0.6124 | MRR@10=0.4921 | R@1=0.3000 | R@3=0.5500 | R@5=0.7500

- separation: mean_pos=1.927 mean_neg=1.296 AUC=0.717 (n=20+180)

- BM25 baseline: n=20 | nDCG@5=0.4408 | nDCG@10=0.5559 | MRR@10=0.4195 | R@1=0.2000 | R@3=0.5000 | R@5=0.6500

- calls: 200 | input tokens: 178,597 | cost: $0.0075
- latency p50=0.47s p95=0.60s (8 workers)
