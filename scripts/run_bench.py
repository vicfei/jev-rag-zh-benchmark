#!/usr/bin/env python3
"""Run the benchmark against OpenRouter /v1/systemone. Stdlib only.

Cost discipline: refuses to start if the key balance is below 2x --max-cost-usd;
aborts mid-run when cumulative logged cost exceeds --max-cost-usd; hard cap on
concurrent workers (8). Every call is logged as one JSONL line.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ENDPOINT = "https://openrouter.ai/api/v1/systemone"
MODEL = "typesafe/jev-1.13-20260917"  # default; override with --model
WORKERS = 8
MODEL_OVERRIDE = None
KEY_OVERRIDE = None
ENDPOINT_OVERRIDE = None
VARIANT_PREFIX = ""
KEY_FILE = Path.home() / ".openrouter_key"

SCORE_ZH = {
    "relevance": {
        "type": "score",
        "instructions": "该段落对回答该查询有多大帮助？",
        "criteria": [
            "不相关：与查询主题无关或未回答查询。",
            "相关但不回答：主题相关，但未回答查询。",
            "部分回答：包含查询答案的一部分。",
            "直接回答：完整回答该查询。",
        ],
    }
}
NOUL_ZH = {"answers": {"type": "noul", "instructions": "仅凭该段落能回答该查询吗？"}}
VARIANTS = {"score-zh": SCORE_ZH, "noul-zh": NOUL_ZH}


def api_key() -> str:
    if os.environ.get("OPENROUTER_API_KEY") or os.environ.get("BENCH_API_KEY"):
        return os.environ.get("BENCH_API_KEY") or os.environ["OPENROUTER_API_KEY"]
    return (KEY_OVERRIDE or KEY_FILE).read_text().strip()


def call(path: str, body: dict | None = None, method: str = "GET") -> tuple[int, dict | str]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        path, data=data, method=method,
        headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw.startswith(("{", "[")) else raw)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, "unparseable"


def _balance_of(d) -> float:
    """Remaining credits from the /key payload (limit None → try /credits upstream)."""
    d = d.get("data", d)
    limit, usage = d.get("limit"), d.get("usage")
    if limit is None:
        return float("inf")
    return float(limit) - float(usage or 0)


def remaining_credits() -> float:
    status, d = call("https://openrouter.ai/api/v1/credits")
    if status == 200 and isinstance(d, dict):
        d = d.get("data", d)
        try:
            return float(d["total_credits"]) - float(d["total_usage"])
        except (KeyError, TypeError, ValueError):
            pass
    return _balance_of(call("https://openrouter.ai/api/v1/key")[1])


def one_call(variant: str, qid: str, pid: str, query: str, passage: str, log_path: Path):
    body = {
        "model": MODEL_OVERRIDE or MODEL,
        "state": {"query": query, "passage": passage},
        "questions": VARIANTS[variant],
    }
    qhash = hashlib.sha256(json.dumps(body["questions"], ensure_ascii=False).encode()).hexdigest()[:12]
    t0 = time.time()
    status, resp = call(ENDPOINT_OVERRIDE or ENDPOINT, body, "POST")
    latency = round(time.time() - t0, 3)
    rec = {
        "ts": time.time(),
        "variant": f"{VARIANT_PREFIX}.{variant}" if VARIANT_PREFIX else variant,
        "qid": qid, "pid": pid,
        "status": status, "latency_s": latency, "qhash": qhash,
        "model": resp.get("model") if isinstance(resp, dict) else None,
        "answer": resp.get("answers") if isinstance(resp, dict) else None,
        "usage": resp.get("usage") if isinstance(resp, dict) else None,
        "error": resp if status != 200 else None,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", required=True, help="data/*.jsonl from prepare_data")
    ap.add_argument("--variant", choices=sorted(VARIANTS), required=True)
    ap.add_argument("--max-cost-usd", type=float, required=True)
    ap.add_argument("--limit", type=int, default=0, help="cap number of queries (0=all)")
    ap.add_argument("--model", default=None, help="override the pinned model id")
    ap.add_argument("--endpoint", default=None,
                    help="override the API endpoint, e.g. a System-One-compatible server "
                         "(balance check and cost metering are OpenRouter-only)")
    ap.add_argument("--key-file", default=None, help="override the key file (default ~/.openrouter_key)")
    ap.add_argument("--variant-prefix", default="",
                    help="prefix log variant names, e.g. 'startlux-27b' -> variant 'startlux-27b.score-zh' "
                         "(keeps analyzer groups separate when several models share a variant wording)")
    args = ap.parse_args()
    global MODEL_OVERRIDE, KEY_OVERRIDE, ENDPOINT_OVERRIDE, VARIANT_PREFIX
    MODEL_OVERRIDE = args.model
    KEY_OVERRIDE = Path(args.key_file).expanduser() if args.key_file else None
    ENDPOINT_OVERRIDE = args.endpoint
    VARIANT_PREFIX = args.variant_prefix
    if args.model:
        print(f"model override: {args.model}")

    if not args.endpoint or "openrouter.ai" in args.endpoint:
        bal = remaining_credits()
        if bal < 2 * args.max_cost_usd:
            sys.exit(f"refusing: remaining balance ${bal:.2f} < 2x budget ${2*args.max_cost_usd:.2f}")
        print(f"balance OK (${bal:.2f}), budget cap ${args.max_cost_usd:.2f}")
    else:
        print(f"custom endpoint {args.endpoint} — skipping OpenRouter balance check")

    sample = [json.loads(l) for l in Path(args.sample).read_text().splitlines() if l.strip()]
    if args.limit:
        sample = sample[: args.limit]
    tasks = [(s["qid"], p["pid"], s["query"], p["text"]) for s in sample for p in s["pool"]]
    tag = ((VARIANT_PREFIX or "") + "." + (MODEL_OVERRIDE or MODEL)) \
        .replace("typesafe/", "").replace("/", "-").replace(".", "")
    log_path = Path("logs") / f"{Path(args.sample).stem}.{args.variant}.{tag}.jsonl"
    log_path.parent.mkdir(exist_ok=True)
    log_path.unlink(missing_ok=True)
    print(f"{len(tasks)} calls → {log_path}")

    spent, done, errors = 0.0, 0, 0
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(one_call, args.variant, *t, log_path) for t in tasks]
        for fut in concurrent.futures.as_completed(futs):
            rec = fut.result()
            done += 1
            u = rec.get("usage") or {}
            spent += float(u.get("cost") or 0)
            if rec["status"] != 200:
                errors += 1
                print(f"  [{done}/{len(tasks)}] {rec['qid']}/{rec['pid']} HTTP {rec['status']}: {str(rec['error'])[:120]}")
            if spent > args.max_cost_usd:
                sys.exit(f"COST BREAKER: ${spent:.4f} > ${args.max_cost_usd:.2f} after {done} calls")
            if done % 100 == 0:
                print(f"  [{done}/{len(tasks)}] spent ${spent:.4f} elapsed {time.time()-t0:.0f}s")
    print(f"DONE {done} calls, {errors} errors, ${spent:.4f}, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
