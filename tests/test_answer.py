"""Answering rules with a fake retriever and a fake model; no Ollama needed."""

import json

import pytest

from irpf_assistant.answer import Answerer, format_passage, load_text, parse_output
from irpf_assistant.retrieve import Hit


def hit(qid: int, distance: float = 0.2, answer: str = "Resposta oficial.") -> Hit:
    return Hit(
        id=qid,
        title=f"Título {qid}",
        question=f"Pergunta {qid}?",
        answer=answer,
        page=100 + qid,
        distance=distance,
    )


class FakeRetriever:
    def __init__(self, hits: list[Hit]) -> None:
        self.hits = hits

    def search(self, query: str, k: int = 5) -> list[Hit]:
        return self.hits[:k]


class FakeChat:
    model = "fake-chat"

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def __call__(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.reply


def reply(found: bool, answer: str, citations: list[int]) -> str:
    return json.dumps({"found": found, "answer": answer, "citations": citations})


def ask(model_reply: str, hits: list[Hit] | None = None, question: str = "Posso deduzir?"):
    chat = FakeChat(model_reply)
    answerer = Answerer(FakeRetriever(hits or [hit(384), hit(380)]), chat, k=3)
    return answerer.ask(question), chat


def test_the_code_renders_the_citations() -> None:
    answer, _ = ask(reply(True, "Sim, se a sessão for feita por fisioterapeuta.", [384]))
    assert answer.found
    assert answer.reason == "answered"
    assert answer.text == "Sim, se a sessão for feita por fisioterapeuta. (Pergunta nº 384)"
    assert answer.citations == (384,)


def test_several_citations_keep_the_model_order_without_repeats() -> None:
    answer, _ = ask(reply(True, "Depende do caso.", [380, 384, 380]))
    assert answer.text == "Depende do caso. (Pergunta nº 380) (Pergunta nº 384)"


def test_citations_outside_the_retrieved_passages_are_dropped() -> None:
    answer, _ = ask(reply(True, "Sim.", [384, 999]))
    assert answer.citations == (384,)


def test_an_answer_citing_only_unretrieved_questions_becomes_not_found() -> None:
    answer, _ = ask(reply(True, "Sim.", [999]))
    assert (answer.found, answer.reason) == (False, "no_valid_citation")
    assert answer.text == load_text("not_found.md")


def test_an_answer_without_citations_becomes_not_found() -> None:
    answer, _ = ask(reply(True, "Sim.", []))
    assert (answer.found, answer.reason) == (False, "no_valid_citation")


def test_the_model_can_say_it_found_nothing() -> None:
    answer, _ = ask(reply(False, "", []))
    assert (answer.found, answer.reason) == (False, "model_not_found")
    assert answer.text == load_text("not_found.md")


@pytest.mark.parametrize(
    "raw", ["not json", "[]", '{"found": "yes", "answer": "", "citations": []}', '{"found": true}']
)
def test_malformed_model_output_becomes_not_found(raw: str) -> None:
    answer, _ = ask(raw)
    assert (answer.found, answer.reason) == (False, "invalid_output")


def test_parse_output_rejects_non_integer_citations() -> None:
    assert parse_output('{"found": true, "answer": "Sim.", "citations": ["384"]}') is None
    assert parse_output('{"found": true, "answer": "Sim.", "citations": [true]}') is None


def test_citations_the_model_writes_in_the_text_are_not_repeated() -> None:
    answer, _ = ask(reply(True, "Pode deduzir (Pergunta nº 384).", [384]))
    assert answer.text == "Pode deduzir. (Pergunta nº 384)"


def test_off_topic_questions_are_refused_without_calling_the_model() -> None:
    answer, chat = ask(reply(True, "Sim.", [384]), hits=[hit(384, distance=0.45)])
    assert (answer.found, answer.reason) == (False, "low_similarity")
    assert chat.calls == []


def test_the_prompt_lists_each_passage_with_its_number_and_the_question() -> None:
    _, chat = ask(reply(True, "Sim.", [384]), question="Quiropraxia é dedutível?")
    system, user = chat.calls[0]
    assert system == load_text("answer_system.md")
    assert (
        "[Pergunta nº 384] Título 384\nPergunta: Pergunta 384?\nResposta: Resposta oficial." in user
    )
    assert "[Pergunta nº 380]" in user
    assert user.endswith("Dúvida do contribuinte: Quiropraxia é dedutível?")


def test_long_answers_are_cut_in_the_prompt() -> None:
    passage = format_passage(hit(1, answer="a" * 50), max_chars=10)
    assert passage.endswith("Resposta: aaaaaaaaaa […]")


def test_the_not_found_text_points_to_the_receita_or_an_accountant() -> None:
    text = load_text("not_found.md")
    assert "Receita Federal" in text
    assert "contador" in text
