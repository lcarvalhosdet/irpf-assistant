"""Compare retrieval configurations on the paraphrased question set.

Usage:
    uv run python evals/run_eval.py --name index-mode

Each run writes one CSV to evals/results/, with one row per configuration, and prints the
queries whose expected question was not in the top 5.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from datetime import date

from irpf_assistant.index import Mode
from irpf_assistant.metrics import hit_at_k, mean_reciprocal_rank, rank_of
from irpf_assistant.paths import ROOT, display_path
from irpf_assistant.retrieve import Retriever

EVAL_SET = ROOT / "evals" / "questions_paraphrased.jsonl"
RESULTS_DIR = ROOT / "evals" / "results"


def git_commit() -> str:
    """Short hash of HEAD, marked "-dirty" when the working tree has uncommitted changes."""
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    return f"{head}-dirty" if dirty.stdout.strip() else head


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True, help="experiment name, used in the CSV name")
    parser.add_argument("--k", type=int, default=10, help="how many results to retrieve")
    args = parser.parse_args()

    with EVAL_SET.open(encoding="utf-8") as file:
        cases = [json.loads(line) for line in file]
    unreviewed = sum(not case["reviewed"] for case in cases)

    rows = []
    for mode in Mode:
        retriever = Retriever(mode)
        ranks = []
        for case in cases:
            ranked = [hit.id for hit in retriever.search(case["query"], k=args.k)]
            rank = rank_of(case["expected_id"], ranked)
            ranks.append(rank)
            if rank is None or rank > 5:
                print(f"{mode}: miss@5 expected {case['expected_id']:03d}, got {ranked[:3]}")
        rows.append(
            {
                "experiment": args.name,
                "config": f"mode={mode}",
                "embedding_model": retriever.embed.model,
                "queries": len(cases),
                "unreviewed": unreviewed,
                "hit@1": round(hit_at_k(ranks, 1), 3),
                "hit@3": round(hit_at_k(ranks, 3), 3),
                "hit@5": round(hit_at_k(ranks, 5), 3),
                f"mrr@{args.k}": round(mean_reciprocal_rank(ranks), 3),
                "date": date.today().isoformat(),
                "commit": git_commit(),
            }
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{date.today().isoformat()}_{args.name}.csv"
    with out.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        metrics = {key: row[key] for key in row if key.startswith(("hit@", "mrr@"))}
        print(f"{row['config']}: {metrics}")
    print(f"results written to {display_path(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
