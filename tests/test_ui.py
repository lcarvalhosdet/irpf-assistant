"""Chat reply formatting, error messages, and one check that the Gradio app builds."""

import pytest

from irpf_assistant import ui
from irpf_assistant.answer import Answer, load_text
from irpf_assistant.retrieve import Hit

HITS = (
    Hit(id=384, title="Quiropraxia", question="Q?", answer="R.", page=188, distance=0.23),
    Hit(
        id=373, title="Internação em residência", question="Q?", answer="R.", page=186, distance=0.3
    ),
)


def make_answer(found: bool, citations: tuple[int, ...]) -> Answer:
    text = "Sim, com condições. (Pergunta nº 384)" if found else load_text("not_found.md")
    return Answer(
        text=text,
        found=found,
        citations=citations,
        hits=HITS,
        reason="answered" if found else "model_not_found",
        retrieval_ms=40.0,
        generation_ms=8200.0,
    )


def test_reply_lists_only_the_cited_questions_as_sources() -> None:
    reply = ui.format_reply(make_answer(True, (384,)), "qwen3.5:9b")

    assert reply.startswith("Sim, com condições. (Pergunta nº 384)")
    assert "**Fontes no guia oficial:**\n- Pergunta nº 384: Quiropraxia (p. 188)" in reply
    assert "Internação" not in reply
    assert reply.endswith("<sub>qwen3.5:9b · 8.2 s</sub>")


def test_reply_for_not_found_has_no_sources() -> None:
    reply = ui.format_reply(make_answer(False, ()), "qwen3.5:4b")
    assert reply.startswith(load_text("not_found.md"))
    assert "Fontes" not in reply


def test_respond_explains_in_portuguese_that_ollama_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def ollama_down(model: str):
        raise ConnectionError

    monkeypatch.setattr(ui, "answerer_for", ollama_down)
    assert "ollama serve" in ui.respond("Posso deduzir quiropraxia?", [], "qwen3.5:9b")


def test_the_ui_builds_with_the_disclaimer_on_screen() -> None:
    demo = ui.build_ui()
    markdown = [block.value for block in demo.blocks.values() if type(block).__name__ == "Markdown"]
    assert any(load_text("disclaimer.md") in text for text in markdown)
