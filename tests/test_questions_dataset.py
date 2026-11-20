"""Checks on the versioned dataset, data/processed/questions.jsonl.

These run in CI, where the source PDF is not available. When the PDF is present locally, one
more test parses it again and fails if the committed dataset is out of date.
"""

import pytest

from irpf_assistant.ingest import Question, parse_pdf, read_jsonl, validate
from irpf_assistant.paths import QUESTIONS_PATH, RAW_PDF


@pytest.fixture(scope="module")
def questions() -> list[Question]:
    return read_jsonl(QUESTIONS_PATH)


def test_has_745_questions(questions: list[Question]) -> None:
    assert len(questions) == 745


def test_ids_are_unique_and_in_order(questions: list[Question]) -> None:
    ids = [question.id for question in questions]
    assert len(set(ids)) == len(ids)
    assert ids == list(range(1, 746))


def test_no_question_or_answer_is_empty(questions: list[Question]) -> None:
    assert [q.id for q in questions if not q.question.strip()] == []
    assert [q.id for q in questions if not q.answer.strip()] == []


def test_every_question_has_a_chapter_and_a_title(questions: list[Question]) -> None:
    assert [q.id for q in questions if not q.chapter.strip() or not q.title.strip()] == []


def test_pages_follow_the_question_order(questions: list[Question]) -> None:
    pages = [question.page for question in questions]
    assert pages == sorted(pages)


def test_dataset_passes_ingest_validation(questions: list[Question]) -> None:
    validate(questions)


@pytest.mark.skipif(not RAW_PDF.exists(), reason="source PDF not downloaded; see data/SOURCE.md")
def test_dataset_matches_a_fresh_parse_of_the_pdf(questions: list[Question]) -> None:
    parsed, _ = parse_pdf(RAW_PDF)
    assert len(parsed) == len(questions)
    assert [new.id for new, old in zip(parsed, questions, strict=True) if new != old] == []
