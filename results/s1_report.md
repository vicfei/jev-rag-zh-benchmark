# s1 results

## noul-zh
- ranking: n=100 | nDCG@5=0.5310 | nDCG@10=0.5876 | MRR@10=0.4580 | R@1=0.2400 | R@3=0.5400 | R@5=0.8300

- separation: mean_pos=0.484 mean_neg=0.257 AUC=0.718 (n=100+900)

## score-zh
- ranking: n=100 | nDCG@5=0.5461 | nDCG@10=0.6019 | MRR@10=0.4765 | R@1=0.2600 | R@3=0.6000 | R@5=0.8300

- separation: mean_pos=1.927 mean_neg=1.258 AUC=0.714 (n=100+900)

- BM25 baseline: n=100 | nDCG@5=0.4127 | nDCG@10=0.5132 | MRR@10=0.3627 | R@1=0.1100 | R@3=0.4900 | R@5=0.6900

- calls: 2000 | input tokens: 1,683,036 | cost: $0.0707
- latency p50=0.47s p95=0.61s (8 workers)
