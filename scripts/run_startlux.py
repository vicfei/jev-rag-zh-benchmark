#!/usr/bin/env python3
"""Run StartLux-Decision (via Bamboo Relay, free tier) on the S1 sample.

Exports logs compatible with analyze.py so the three-way table
(Jev / StartLux / BM25) drops out unchanged.

Auth: BAMBOO_API_KEY env or ~/.secrets/bamboo_key (free tier, no top-up).
Endpoint per relay docs: POST https://api.bamboonode.dev/v1/decisions
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import random
import time
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "https://api.bamboonode.dev/v1/decisions"
DEFAULT_MODEL = "startlux-decision-27b-autothink"
KEY_FILE = Path.home() / ".secrets" / "bamboo_key"

# Frozen from the Jev runs — must stay byte-identical for comparability.
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
    if os.environ.get("BAMBOO_API_KEY"):
        return os.environ["BAMBOO_API_KEY"]
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    raise SystemExit("no Bamboo key: set BAMBOO_API_KEY or write ~/.secrets/bamboo_key "
                     "(free tier at https://bamboonode.dev/register — no top-up required)")


def call(body: dict, retries: int = 4) -> tuple[int, dict]:
    for attempt in range(retries):
        req = urllib.request.Request(
            ENDPOINT, data=json.dumps(body).encode(), method="POST",
            headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2 ** attempt + random.random())
                continue
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, {"raw": raw[:500]}
        except Exception as e:  # noqa: BLE001 - transport failure: retry once more
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return 0, {"error": str(e)}
    return 0, {"error": "retries exhausted"}


def extract_score(resp: dict, qid: str) -> float | None:
    ans = (resp.get("answers") or {}).get(qid) or {}
    if ans.get("type") == "score":
        return float(ans.get("score", 0))
    if "score" in ans:
        return float(ans["score"])
    return None


def extract_noul(resp: dict, qid: str) -> float | None:
    ans = (resp.get("answers") or {}).get(qid) or {}
    if ans.get("type") == "noul":
        return float(ans.get("noul", 0))
    if "noul" in ans:
        return float(ans["noul"])
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="data/s1.jsonl")
    ap.add_argument("--variant", choices=sorted(VARIANTS), default="score-zh")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=0, help="cap queries (0=all; use 3 for schema dry-run)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    sample = [json.loads(l) for l in Path(args.sample).read_text().splitlines() if l.strip()]
    if args.limit:
        sample = sample[: args.limit]
    qid = next(iter(VARIANTS[args.variant]))
    extract = extract_score if VARIANTS[args.variant] == SCORE_ZH else extract_noul

    tasks = [(s["qid"], p["pid"], s["query"], p["text"]) for s in sample for p in s["pool"]]
    out = Path(args.out or f"logs/{Path(args.sample).stem}.{args.variant}.{args.model.replace('/', '-')}.jsonl")
    out.parent.mkdir(exist_ok=True)
    out.unlink(missing_ok=True)
    print(f"{len(tasks)} calls → {out}")

    first_error = None
    done = errors = 0
    t0 = time.time()

    def one(q, pid, query, passage):
        body = {"model": args.model,
                "state": {"query": query, "passage": passage},
                "questions": VARIANTS[args.variant]}
        st, resp = call(body)
        rec = {
            "ts": time.time(), "variant": f"startlux-{args.model.split('-')[-3] if '27b' in args.model else 'x'}",
            "qid": q, "pid": pid, "status": st,
            "model": resp.get("model"),
            "answer": {"answers": {qid: ({"type": "score", "score": extract(resp, qid)}
                                     if VARIANTS[args.variant] == SCORE_ZH else
                                     {"type": "noul", "noul": extract(resp, qid)})}},
            "usage": resp.get("usage"),
            "error": None if st == 200 else resp,
        }
        return rec

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:  # conservative for free tier
        futs = [ex.submit(one, *t) for t in tasks]
        with open(out, "a", encoding="utf-8") as f:
            for fut in concurrent.futures.as_completed(futs):
                rec = fut.result()
                done += 1
                if rec["status"] != 200:
                    errors += 1
                    if first_error is None:
                        first_error = rec["error"]
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                if done % 100 == 0:
                    print(f"  [{done}/{len(tasks)}] {time.time()-t0:.0f}s errors={errors}")
    print(f"DONE {done} calls, {errors} errors, {time.time()-t0:.0f}s")
    if first_error is not None and errors:
        print(f"first error: {json.dumps(first_error, ensure_ascii=False)[:300]}")
        print("hint: run --limit 3 first to inspect the response schema if every call errors")


if __name__ == "__main__":
    main()
