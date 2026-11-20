"""Index building with a fake embedder, so these tests need neither Ollama nor a GPU."""

from pathlib import Path

import lancedb
import pytest

from irpf_assistant.index import CONTEXT_TOKENS, Embedding, Mode, build_table, document_text
from irpf_assistant.ingest import Question


class FakeEmbedder:
    model = "fake-embedder"

    def __call__(self, text: str) -> Embedding:
        tokens = min(len(text.split()), CONTEXT_TOKENS)
        return Embedding(vector=[float(len(text)), 1.0, 0.0, 0.0], tokens=tokens)


def make_question(qid: int, answer: str = "Sim.") -> Question:
    return Question(
        id=qid,
        chapter="CAPÍTULO",
        title=f"Título {qid}",
        question=f"Pergunta {qid}?",
        answer=answer,
        page=22 + qid,
    )


def test_document_text_depends_on_the_mode() -> None:
    question = make_question(1, answer="Resposta completa.")
    assert document_text(question, Mode.QUESTION) == "Pergunta 1?"
    assert document_text(question, Mode.QUESTION_ANSWER) == "Pergunta 1?\nResposta completa."


@pytest.mark.parametrize("mode", list(Mode))
def test_build_table_writes_one_row_per_question(tmp_path: Path, mode: Mode) -> None:
    db = lancedb.connect(tmp_path)
    questions = [make_question(1), make_question(2)]

    report = build_table(db, mode, questions, FakeEmbedder())

    table = db.open_table(mode.value)
    rows = table.to_arrow().to_pylist()
    assert (report.rows, table.count_rows()) == (2, 2)
    assert [row["id"] for row in rows] == [1, 2]
    assert rows[1]["text"] == document_text(questions[1], mode)
    assert rows[1]["answer"] == "Sim."
    assert len(rows[0]["vector"]) == 4
    metadata = table.schema.metadata
    assert metadata[b"embedding_model"] == b"fake-embedder"
    assert metadata[b"mode"] == mode.value.encode()


def test_build_table_counts_texts_cut_at_the_context_limit(tmp_path: Path) -> None:
    long_answer = " ".join(["palavra"] * (CONTEXT_TOKENS + 100))
    questions = [make_question(1), make_question(2, answer=long_answer)]

    report = build_table(lancedb.connect(tmp_path), Mode.QUESTION_ANSWER, questions, FakeEmbedder())

    assert report.truncated == 1


def test_rebuilding_replaces_the_table(tmp_path: Path) -> None:
    db = lancedb.connect(tmp_path)
    build_table(db, Mode.QUESTION, [make_question(1), make_question(2)], FakeEmbedder())
    build_table(db, Mode.QUESTION, [make_question(1)], FakeEmbedder())
    assert db.open_table(Mode.QUESTION.value).count_rows() == 1


def test_build_table_rejects_an_empty_question_list(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no questions"):
        build_table(lancedb.connect(tmp_path), Mode.QUESTION, [], FakeEmbedder())


def test_build_table_reports_progress(tmp_path: Path) -> None:
    seen: list[tuple[int, int]] = []
    build_table(
        lancedb.connect(tmp_path),
        Mode.QUESTION,
        [make_question(1), make_question(2)],
        FakeEmbedder(),
        on_progress=lambda done, total: seen.append((done, total)),
    )
    assert seen == [(1, 2), (2, 2)]
