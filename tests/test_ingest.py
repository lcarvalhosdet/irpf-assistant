"""Unit tests for the ingest parser on small synthetic inputs; no PDF needed."""

import pytest

from irpf_assistant.ingest import (
    END_OF_ANSWER,
    Block,
    IngestError,
    Line,
    Question,
    clean,
    join_lines,
    merge,
    normalize_title,
    parse_body,
    validate,
)


def block(*lines: str, bold: bool = False, size: float = 10.0, page: int = 30) -> Block:
    return Block(page=page, lines=tuple(Line(text, bold) for text in lines), size=size)


def question_blocks(number: int, heading: str) -> list[Block]:
    return [
        block(heading, bold=True),
        block(f"{number:03d} — {heading.capitalize()}?", bold=True),
        block("Sim."),
        block(END_OF_ANSWER),
    ]


def drafts_for(*headings: str):
    return parse_body(
        [
            b
            for number, heading in enumerate(headings, start=1)
            for b in question_blocks(number, heading)
        ]
    )


def make_question(qid: int, **overrides: object) -> Question:
    fields = {
        "id": qid,
        "chapter": "CAPÍTULO",
        "title": "Título",
        "question": "Pergunta?",
        "answer": "Resposta.",
        "page": 23,
    }
    return Question(**(fields | overrides))


def test_clean_normalizes_spaces_and_drops_soft_hyphens() -> None:
    assert clean(" R$\xa0800.000,00\n (oitocentos   mil) ") == "R$ 800.000,00 (oitocentos mil)"
    assert clean("decla\xadração") == "declaração"


def test_join_lines_keeps_hyphenated_compounds_together() -> None:
    lines = ["perdas de anos-", "calendário anteriores"]
    assert join_lines(lines) == "perdas de anos-calendário anteriores"


def test_join_lines_keeps_spaced_dashes_apart() -> None:
    assert join_lines(["Declaração de Ajuste Anual -", "DAA"]) == "Declaração de Ajuste Anual - DAA"


def test_normalize_title_ignores_case_dashes_quotes_and_spacing() -> None:
    contents = "“Meu Imposto de Renda” \N{EN DASH} Vedações à sua utilização"
    heading = '"MEU IMPOSTO DE RENDA" - VEDAÇÕES À SUA UTILIZAÇÃO'
    assert normalize_title(contents) == normalize_title(heading)
    assert normalize_title("Filho (a)") == normalize_title("FILHO(A)")
    assert normalize_title("Lei nº 14.973, de 2023") != normalize_title("LEI Nº 14.973, DE 2024")


def test_parse_body_cuts_chapters_titles_questions_and_answers() -> None:
    blocks = [
        block("OBRIGATORIEDADE DE", "APRESENTAÇÃO", bold=True, size=14),
        block("OBRIGATORIEDADE", bold=True),
        block("001 — Quem está obrigado a apresentar", "a declaração?", bold=True, page=23),
        block("Está obrigada a pessoa física que", "recebeu rendimentos tributáveis."),
        block("(Instrução Normativa RFB nº 2.312, de 13 de março de 2026)"),
        block(END_OF_ANSWER),
        block("PESSOA FÍSICA DESOBRIGADA", bold=True),
        block("002 —Pessoa física desobrigada pode declarar?", bold=True, page=24),
        block("Sim."),
        block(END_OF_ANSWER),
    ]

    first, second = parse_body(blocks)

    assert (first.id, first.page) == (1, 23)
    assert first.chapter == "OBRIGATORIEDADE DE APRESENTAÇÃO"
    assert first.body_title == "OBRIGATORIEDADE"
    assert first.question == "Quem está obrigado a apresentar a declaração?"
    assert first.answer == [
        "Está obrigada a pessoa física que recebeu rendimentos tributáveis.",
        "(Instrução Normativa RFB nº 2.312, de 13 de março de 2026)",
    ]
    assert (second.id, second.page, second.chapter) == (2, 24, first.chapter)
    assert second.question == "Pessoa física desobrigada pode declarar?"
    assert second.answer == ["Sim."]


def test_question_ends_at_its_question_mark_when_the_answer_opens_in_bold() -> None:
    blocks = [
        block("RETIFICAÇÃO", bold=True),
        block(
            "050 — Como proceder na",
            "declaração retificadora?",
            "1 - Quando a retificação reduzir o imposto:",
            bold=True,
        ),
        block("observar o procedimento a seguir."),
        block(END_OF_ANSWER),
    ]

    (draft,) = parse_body(blocks)

    assert draft.question == "Como proceder na declaração retificadora?"
    assert draft.answer == [
        "1 - Quando a retificação reduzir o imposto:",
        "observar o procedimento a seguir.",
    ]


def test_parse_body_rejects_plain_text_between_questions() -> None:
    blocks = [*question_blocks(1, "TEMA"), block("texto solto fora de qualquer resposta")]
    with pytest.raises(IngestError, match="unexpected text between questions"):
        parse_body(blocks)


def test_merge_uses_the_contents_title_when_it_matches_the_heading() -> None:
    questions, warnings = merge(
        drafts_for("PESSOA FÍSICA DESOBRIGADA"), [(1, "Pessoa física desobrigada")]
    )
    assert questions[0].title == "Pessoa física desobrigada"
    assert warnings == []


def test_merge_keeps_the_heading_and_warns_when_the_contents_disagree() -> None:
    headings = [f"TEMA {n}" for n in range(1, 20)] + ["LEI Nº 14.973, DE 2024"]
    contents = [(n, f"Tema {n}") for n in range(1, 20)] + [(19, "Lei nº 14.973, de 2023")]

    questions, warnings = merge(drafts_for(*headings), contents)

    assert questions[-1].title == "LEI Nº 14.973, DE 2024"
    assert warnings == [
        "question 020 is numbered 019 in the contents",
        "question 020 title: contents 'Lei nº 14.973, de 2023', body 'LEI Nº 14.973, DE 2024'",
    ]


def test_merge_fails_when_the_pairing_slips() -> None:
    with pytest.raises(IngestError, match="pairing is off"):
        merge(drafts_for("ALFA", "BETA", "GAMA"), [(1, "Beta"), (2, "Gama"), (3, "Delta")])


def test_merge_fails_when_counts_differ() -> None:
    with pytest.raises(IngestError, match="2 entries, body has 1"):
        merge(drafts_for("ALFA"), [(1, "Alfa"), (2, "Beta")])


def test_validate_accepts_a_complete_sequence() -> None:
    validate([make_question(1), make_question(2)], expected=2)


@pytest.mark.parametrize(
    ("questions", "message"),
    [
        ([make_question(1)], "expected 2 questions, found 1"),
        ([make_question(1), make_question(3)], "not unique and sequential"),
        ([make_question(1), make_question(1)], "not unique and sequential"),
        ([make_question(1), make_question(2, answer="")], "question 002 has empty answer"),
    ],
)
def test_validate_reports_each_problem(questions: list[Question], message: str) -> None:
    with pytest.raises(IngestError, match=message):
        validate(questions, expected=2)
