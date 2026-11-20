"""Turn the official IRPF Q&A PDF into one JSON line per question.

The guide is a Word export with no PDF outline, so its structure comes from typography:

- chapter headings use a 14 pt font; everything else in the body is 10 pt;
- each question has a bold upper-case title, then a bold line "NNN — question text";
- the answer is the text that follows, closed by a "Retorno ao sumário" link.

The table of contents lists every question with a sentence-case title on the left and its
number on the right margin. It is parsed separately and paired with the body in order: it
supplies the sentence-case titles and an independent check of the body parse. The check is
already useful in the 2026 guide, whose table of contents prints question 424 as "423".

Run ``uv run irpf-ingest`` to rebuild ``data/processed/questions.jsonl``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pymupdf

from irpf_assistant.paths import QUESTIONS_PATH, RAW_PDF, display_path

EXPECTED_QUESTIONS = 745

BOLD_FLAG = 16  # bit 4 of a PyMuPDF span's "flags"
CHAPTER_MIN_SIZE = 13.0
QUESTION_START = re.compile(r"(\d{3})\s*[\N{EM DASH}\N{EN DASH}-]\s*(.*)")
TOC_NUMBER = re.compile(r"\d{3}")
END_OF_ANSWER = "Retorno ao sumário"


class IngestError(ValueError):
    """The PDF did not parse into the expected set of questions."""


@dataclass(frozen=True)
class Question:
    id: int
    chapter: str
    title: str
    question: str
    answer: str
    page: int


@dataclass(frozen=True)
class Line:
    text: str
    bold: bool


@dataclass(frozen=True)
class Block:
    """A paragraph as PyMuPDF groups it: one or more lines on a single page."""

    page: int  # 1-based; matches the page number printed in the guide
    lines: tuple[Line, ...]
    size: float  # largest font size in the block

    @property
    def text(self) -> str:
        return join_lines(line.text for line in self.lines)

    @property
    def bold(self) -> bool:
        return all(line.bold for line in self.lines)


@dataclass
class _Draft:
    id: int
    chapter: str
    body_title: str
    page: int
    question: str
    answer: list[str] = field(default_factory=list)


@dataclass
class _TocEntry:
    number: int  # as printed, which is not always right
    centre: float
    lines: list[tuple[float, str]] = field(default_factory=list)

    @property
    def title(self) -> str:
        return join_lines(text for _, text in sorted(self.lines))


def clean(text: str) -> str:
    """Normalize Unicode and whitespace without changing the published wording."""
    text = unicodedata.normalize("NFC", text).replace("\xa0", " ").replace("\xad", "")
    return re.sub(r"\s+", " ", text).strip()


def join_lines(lines: Iterable[str]) -> str:
    """Join the wrapped lines of one paragraph, keeping compounds such as "ano-calendário"."""
    joined = ""
    for raw in lines:
        line = clean(raw)
        if not line:
            continue
        if not joined:
            joined = line
        elif re.search(r"\w-$", joined) and line[0].islower():
            joined += line
        else:
            joined += " " + line
    return joined


def is_upper(text: str) -> bool:
    return any(char.isalpha() for char in text) and text == text.upper()


def match_question_start(block: Block) -> re.Match[str] | None:
    first = block.lines[0]
    return QUESTION_START.fullmatch(clean(first.text)) if first.bold else None


def read_blocks(page: pymupdf.Page) -> list[Block]:
    """Return the page's text blocks in reading order, without the printed page number."""
    blocks = []
    for raw in page.get_text("dict", sort=True)["blocks"]:
        lines, sizes = [], []
        for raw_line in raw.get("lines", []):
            spans = [span for span in raw_line["spans"] if span["text"].strip()]
            if not spans:
                continue
            text = "".join(span["text"] for span in raw_line["spans"])
            lines.append(Line(text=text, bold=all(span["flags"] & BOLD_FLAG for span in spans)))
            sizes.extend(span["size"] for span in spans)
        if not lines:
            continue
        block = Block(page=page.number + 1, lines=tuple(lines), size=max(sizes))
        is_page_number = block.text.isdigit() and raw["bbox"][1] > 0.9 * page.rect.height
        if not is_page_number:
            blocks.append(block)
    return blocks


def parse_toc(pages: Iterable[pymupdf.Page]) -> list[tuple[int, str]]:
    """Return the table of contents as (printed number, title) pairs, in reading order.

    Titles sit on the left margin and numbers on the right, vertically centred on their
    title, so each title line goes to the number whose centre is closest to its own.
    Chapter names are the bold upper-case lines; a few titles are bold too ("Leasing").
    When a title ends a page and its number opens the next one, that number finds no title
    line on its own page and takes the last line of the previous page.
    """
    entries: list[_TocEntry] = []
    for page in pages:
        page_entries: list[_TocEntry] = []
        title_lines: list[tuple[float, str]] = []
        for raw in page.get_text("dict")["blocks"]:
            for raw_line in raw.get("lines", []):
                spans = [span for span in raw_line["spans"] if span["text"].strip()]
                if not spans:
                    continue
                text = clean("".join(span["text"] for span in raw_line["spans"]))
                x0, y0, _, y1 = raw_line["bbox"]
                centre = (y0 + y1) / 2
                is_chapter = all(span["flags"] & BOLD_FLAG for span in spans) and is_upper(text)
                if TOC_NUMBER.fullmatch(text) and x0 > 0.75 * page.rect.width:
                    page_entries.append(_TocEntry(number=int(text), centre=centre))
                elif x0 < 0.25 * page.rect.width and not is_chapter:
                    title_lines.append((centre, text))
        if not page_entries:
            continue
        for centre, text in title_lines:
            nearest = min(page_entries, key=lambda entry: abs(entry.centre - centre))
            nearest.lines.append((centre, text))
        page_entries.sort(key=lambda entry: entry.centre)
        if entries and not page_entries[0].lines and len(entries[-1].lines) > 1:
            entries[-1].lines.sort()
            page_entries[0].lines.append(entries[-1].lines.pop())
        entries.extend(page_entries)
    return [(entry.number, entry.title) for entry in entries]


def parse_body(blocks: Iterable[Block]) -> list[_Draft]:
    """Walk the body blocks in order and cut them into questions."""
    drafts: list[_Draft] = []
    chapter = ""
    title: list[str] = []
    in_answer = False
    previous_was_chapter = False

    for block in blocks:
        text = block.text
        if block.size >= CHAPTER_MIN_SIZE:
            chapter = f"{chapter} {text}" if previous_was_chapter else text
            previous_was_chapter = True
            title, in_answer = [], False
            continue
        previous_was_chapter = False

        start = match_question_start(block)
        if start:
            # The question runs over the following bold lines up to its "?"; some answers
            # open with a bold item of their own (question 050).
            question = [start[2]]
            rest = list(block.lines[1:])
            while rest and rest[0].bold and not question[-1].rstrip().endswith("?"):
                question.append(rest.pop(0).text)
            draft = _Draft(
                id=int(start[1]),
                chapter=chapter,
                body_title=join_lines(title),
                page=block.page,
                question=join_lines(question),
            )
            if rest:
                draft.answer.append(join_lines(line.text for line in rest))
            drafts.append(draft)
            title, in_answer = [], True
        elif in_answer and text == END_OF_ANSWER:
            in_answer = False
        elif in_answer:
            drafts[-1].answer.append(text)
        elif block.bold:
            title.append(text)
        else:
            raise IngestError(f"page {block.page}: unexpected text between questions: {text!r}")
    return drafts


def normalize_title(title: str) -> str:
    """Reduce a title to its letters and digits, so case, dashes and quotes do not count."""
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFC", title).casefold())


def merge(
    drafts: Sequence[_Draft], toc: Sequence[tuple[int, str]]
) -> tuple[list[Question], list[str]]:
    """Pair body questions with table-of-contents entries in order.

    The sentence-case title from the table of contents is used when it matches the heading
    above the question; otherwise the heading wins, because the body is the authoritative
    text (it is right where the contents get a number or a year wrong). Both kinds of
    disagreement come back as warnings. Many title disagreements mean the pairing slipped.
    """
    if len(toc) != len(drafts):
        raise IngestError(f"table of contents has {len(toc)} entries, body has {len(drafts)}")

    questions, warnings = [], []
    title_mismatches = 0
    for draft, (printed, toc_title) in zip(drafts, toc, strict=True):
        if printed != draft.id:
            warnings.append(f"question {draft.id:03d} is numbered {printed:03d} in the contents")
        title = toc_title
        if normalize_title(toc_title) != normalize_title(draft.body_title):
            title_mismatches += 1
            warnings.append(
                f"question {draft.id:03d} title: contents {toc_title!r}, body {draft.body_title!r}"
            )
            title = draft.body_title
        questions.append(
            Question(
                id=draft.id,
                chapter=draft.chapter,
                title=title,
                question=draft.question,
                answer="\n".join(draft.answer),
                page=draft.page,
            )
        )
    if title_mismatches > 0.1 * len(drafts):
        raise IngestError(
            f"{title_mismatches} titles differ between contents and body; the pairing is off"
        )
    return questions, warnings


def validate(questions: Sequence[Question], expected: int = EXPECTED_QUESTIONS) -> None:
    """Raise IngestError unless ids run 1..expected in order and no field is empty."""
    problems = []
    ids = [question.id for question in questions]
    if len(questions) != expected:
        problems.append(f"expected {expected} questions, found {len(questions)}")
    if ids != list(range(1, len(ids) + 1)):
        problems.append("ids are not unique and sequential from 1")
    for question in questions:
        empty = [name for name, value in asdict(question).items() if value in ("", None)]
        if empty:
            problems.append(f"question {question.id:03d} has empty {', '.join(empty)}")
    if problems:
        raise IngestError("; ".join(problems))


def parse_pdf(path: Path) -> tuple[list[Question], list[str]]:
    """Parse the guide; returns the questions and the title mismatches worth a look."""
    with pymupdf.open(path) as doc:
        pages = [read_blocks(page) for page in doc]
        body_start = next(
            index
            for index, blocks in enumerate(pages)
            if any(match_question_start(block) for block in blocks)
        )
        toc = parse_toc(doc[index] for index in range(body_start))
    drafts = parse_body(block for blocks in pages[body_start:] for block in blocks)
    return merge(drafts, toc)


def write_jsonl(questions: Iterable[Question], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for question in questions:
            file.write(json.dumps(asdict(question), ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[Question]:
    with path.open(encoding="utf-8") as file:
        return [Question(**json.loads(line)) for line in file]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", type=Path, default=RAW_PDF, help="source PDF")
    parser.add_argument("--out", type=Path, default=QUESTIONS_PATH, help="output JSONL")
    parser.add_argument("-v", "--verbose", action="store_true", help="list every warning")
    args = parser.parse_args(argv)

    try:
        questions, warnings = parse_pdf(args.pdf)
        validate(questions)
    except IngestError as error:
        print(f"ingest failed: {error}", file=sys.stderr)
        return 1

    write_jsonl(questions, args.out)
    if args.verbose:
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
    elif warnings:
        print(
            f"{len(warnings)} contents/body disagreements; run with --verbose to list them",
            file=sys.stderr,
        )
    first, last = questions[0].page, questions[-1].page
    print(f"wrote {len(questions)} questions (pages {first}-{last}) to {display_path(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
