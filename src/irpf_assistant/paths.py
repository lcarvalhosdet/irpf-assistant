"""Filesystem locations shared by the pipeline, resolved from the repository root."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_PDF = DATA_DIR / "raw" / "p-r-irpf-2026-v1-00-2026-04-23.pdf"
QUESTIONS_PATH = DATA_DIR / "processed" / "questions.jsonl"
