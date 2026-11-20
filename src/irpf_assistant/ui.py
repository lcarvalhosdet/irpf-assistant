"""Chat UI in Gradio, with the fixed disclaimer on screen.

Each question is answered on its own: the chat shows the history but does not use it as
context. Run ``uv run irpf-ui`` and open http://127.0.0.1:7860. The server listens on
localhost only, and Gradio's usage analytics are switched off.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import ollama

from irpf_assistant.answer import Answer, Model, answerer_for, load_text

if TYPE_CHECKING:
    import gradio as gr

DISCLAIMER = load_text("disclaimer.md")
MODEL_CHOICES = [
    ("Qualidade (qwen3.5:9b)", Model.QUALITY.value),
    ("Velocidade (qwen3.5:4b)", Model.SPEED.value),
]
EXAMPLES = [
    "Posso deduzir sessões de quiropraxia?",
    "Ganhei um prêmio de loteria. Preciso declarar?",
    "Usei o FGTS para quitar meu apartamento. Como informo isso na declaração?",
    "Vender ações na bolsa é isento até quanto por mês?",
]


def format_reply(answer: Answer, model: str) -> str:
    """The chat message: the answer, the questions it cites and how long it took."""
    lines = [answer.text]
    cited = [hit for hit in answer.hits if hit.id in answer.citations]
    if cited:
        lines += ["", "**Fontes no guia oficial:**"]
        lines += [f"- Pergunta nº {hit.id:03d}: {hit.title} (p. {hit.page})" for hit in cited]
    seconds = (answer.retrieval_ms + answer.generation_ms) / 1000
    lines += ["", f"<sub>{model} · {seconds:.1f} s</sub>"]
    return "\n".join(lines)


def respond(message: str, history: list[dict], model: str) -> str:
    try:
        return format_reply(answerer_for(model).ask(message), model)
    except ConnectionError:
        return "O Ollama não está rodando. Inicie com `ollama serve` e tente de novo."
    except ollama.ResponseError as error:
        return f"O Ollama recusou o pedido ({error.error}). O modelo {model} foi baixado?"
    except ValueError:
        return "O índice não foi encontrado. Gere com `uv run irpf-index` e tente de novo."


def build_ui() -> gr.Blocks:
    # Gradio takes seconds to import, so it is imported here rather than at module load,
    # which keeps the API and most tests fast.
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    import gradio as gr

    with gr.Blocks(title="Dúvidas sobre o IRPF 2026", analytics_enabled=False) as demo:
        gr.Markdown(
            "# Dúvidas sobre o IRPF 2026\n"
            'Respostas tiradas do guia oficial "Perguntas e Respostas IRPF 2026", da Receita '
            "Federal, sempre com o número da pergunta usada."
        )
        gr.Markdown(f"> **Aviso:** {DISCLAIMER}")
        model = gr.Radio(MODEL_CHOICES, value=Model.QUALITY.value, label="Modelo")
        gr.ChatInterface(
            fn=respond,
            chatbot=gr.Chatbot(label="Conversa", height=420),
            textbox=gr.Textbox(
                placeholder="Digite sua dúvida sobre o IRPF 2026...",
                show_label=False,
                submit_btn=True,
            ),
            additional_inputs=[model],
            examples=[[question, Model.QUALITY.value] for question in EXAMPLES],
            examples_label="Exemplos",
            cache_examples=False,
            flagging_mode="never",
            analytics_enabled=False,
            save_history=False,
        )
        gr.Markdown(
            "<sub>Cada pergunta é respondida de forma independente. "
            "Tudo roda neste computador, sem enviar dados para fora.</sub>"
        )
    return demo


def main() -> None:
    build_ui().launch(server_name="127.0.0.1", server_port=7860)


if __name__ == "__main__":
    main()
