# ADR 0003: Version the parsed dataset

- Status: accepted
- Date: 2026-11-20

## Context

The working agreement keeps the source PDF and generated files out of git. CI, however, has to
check the dataset and evaluate retrieval, and it should not depend on the Receita Federal
website being up.

## Decision

Commit `data/processed/questions.jsonl` (745 lines, about 1.2 MB), the one generated file in the
repository. Indexes, caches and models stay ignored. The PDF stays out of git, and
`data/SOURCE.md` records its URL, version and SHA-256 so it can be downloaded again.

## Consequences

- CI can test the dataset (745 questions, ids 1 to 745 in order, no empty field) and run the
  retrieval evaluation without the PDF.
- A parser change shows up as a reviewable diff of the dataset.
- When the PDF is present locally, a test parses it again and fails if the committed dataset is
  stale.
- The guide allows reproducing it in whole or in part as long as the source is cited. The text is
  kept as published, and `data/SOURCE.md` cites the source.
