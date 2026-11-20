# Evaluation

## Question set

`questions_paraphrased.jsonl` has one JSON object per line:

| Field | Meaning |
|---|---|
| `query` | A question as a taxpayer would type it, in Portuguese |
| `expected_id` | Number of the official question that answers it |
| `source` | `llm` (drafted by an LLM) or `human` (written by hand) |
| `reviewed` | `true` once a person has checked the query and its expected id |

The first 30 queries are a seed set drafted by an LLM from questions spread evenly through the
guide (`round(12 + i * 745 / 30)` for `i` from 0 to 29: ids 12, 37, …, 732), so the sample
follows the size of each chapter. Week 2 grows the set to about 100 queries, part of them
written by hand.

## Running

```bash
uv run python evals/run_eval.py --name index-mode
```

Each run writes one CSV to `results/`, with one row per configuration: hit@1, hit@3, hit@5 and
MRR@10, the embedding model, the size of the question set, how many queries are still
unreviewed, the date and the git commit.
