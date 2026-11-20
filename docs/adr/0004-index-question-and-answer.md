# ADR 0004: One vector per question, embedding the question with its answer

- Status: accepted; to be re-checked with the full evaluation set in week 2
- Date: 2026-11-20

## Context

Step 3 of the plan compares two ways to index the 745 questions, one vector each:

- `question`: embed only the official question (median 28 tokens);
- `question_answer`: embed the question followed by its answer (median 213 tokens).

`granite-embedding:278m` returns 768-dimension unit vectors and reads at most 512 tokens, so
117 of the 745 `question_answer` texts (15.7%) are cut short.

The comparison uses a seed set of 30 paraphrased questions (`evals/questions_paraphrased.jsonl`):
taxpayer-style queries drafted by an LLM from questions spread evenly through the guide, each
reviewed together with its expected answer. The full set, about 100 queries, comes in week 2.

## Results

Run `evals/results/2026-11-20_index-mode.csv` (commit 9453a98), exact search by cosine distance:

| Index | hit@1 | hit@3 | hit@5 | MRR@10 |
|---|---|---|---|---|
| `question` | 0.567 | 0.667 | 0.800 | 0.657 |
| `question_answer` | **0.633** | **0.900** | **0.933** | **0.761** |

Query by query, `question_answer` ranks the expected question higher in 11 queries and lower in
3, each loss by one or two positions; the other 16 tie. A sign test gives p ≈ 0.06: a consistent
signal, though 30 queries are not yet proof.

## Decision

Retrieval uses the `question_answer` table by default. Both tables stay in the index, so the
comparison can run again after every change.

## Consequences

- The answer widens what each vector covers. The largest gains come on scenario-style queries
  worded far from the official question: question 534 moves from rank 21 to 2, and 583 from 6 to 1.
- Truncation did not stop `question_answer` from winning, but 15.7% of the answers are only
  partly represented. Splitting long answers into chunks belongs to the "per question × fixed
  size" experiment planned for week 2.
- Generic queries are still weak. In a spot check outside the seed set, "Quem é obrigado a fazer
  a declaração do imposto de renda?" put question 001 at rank 42 (`question`) and 30
  (`question_answer`). Hybrid search (BM25 plus vectors) and a reranker, both in the plan,
  target this.
- Both tables rebuild in about 30 seconds (8 s and 22 s) and take 6.3 MB; they stay out of git.
