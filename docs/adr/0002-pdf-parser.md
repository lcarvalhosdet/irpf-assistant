# ADR 0002: Parse the guide with PyMuPDF, from its typography

- Status: accepted
- Date: 2026-11-20
- Settles the PDF parser left open in [ADR 0001](0001-initial-stack.md).

## Context

The parser had to be whichever of PyMuPDF and Docling better preserves the question numbering
and the boundaries between questions. The 2026 guide (version 1.00, 340 pages) is a Microsoft
Word export with no PDF outline, but its typography is regular:

- chapter headings are 14 pt; the rest of the body is 10 pt;
- each question has a bold heading, then a bold line "NNN — question";
- the answer is the text that follows, closed by a "Retorno ao sumário" link.

The table of contents (pages 6–22) lists every question again, with a sentence-case title on
the left and its number on the right margin.

## Decision

Use PyMuPDF and read the structure from font size and weight:

- a small state machine cuts the body (pages 23–339) into questions;
- the table of contents is parsed on its own and paired with the body in order. The counts
  must match, and every number or title disagreement is reported;
- the ingest fails unless it finds exactly 745 questions numbered 1 to 745, with no empty field.

Docling was not tried. PyMuPDF already recovers all 745 questions with the right numbers and
boundaries, so Docling could at best tie on the criterion, while adding PyTorch and layout
models to the install.

## Consequences

- Parsing takes about 3 seconds and needs no model.
- The cross-check surfaced real errors in the source: the table of contents prints question 424
  as "423", and 26 titles differ from the heading above the question (for example, "Lei nº
  14.973, de 2023" against "DE 2024"). In those cases the heading wins, since the body is the
  authoritative text; the other 719 titles keep the contents' sentence case.
- Tables come out flattened to one line per row, with cells separated by spaces. That is enough
  for retrieval; PyMuPDF's table extraction is the next step if answers about tables suffer.
- Answers run from 33 to 21,637 characters (median 716). Step 3 has to account for that when it
  chunks and embeds them.
- PyMuPDF is dual-licensed: AGPL 3.0 or a commercial license from Artifex. AGPL fits this public
  open-source repository; a closed-source product would need the commercial license or another
  parser.
- PyMuPDF 2.1 also installs pymupdf-layout and pymupdf4llm, with onnxruntime, numpy and networkx,
  which this parser does not use.
