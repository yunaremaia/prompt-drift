"""Scanner para arquivos de prompt e avaliação."""

import re
from pathlib import Path
from typing import NamedTuple

PROMPT_EXTENSIONS = {".prompt", ".txt", ".md", ".yaml", ".yml"}
EVAL_EXTENSIONS = {".py", ".eval", ".json", ".yaml", ".yml"}

PROMPT_KEYWORDS = re.compile(
    r"(?i)(prompt|instruction|system|user-message|assistant-message|few-shot|example)",
    re.IGNORECASE,
)

EVAL_KEYWORDS = re.compile(
    r"(?i)(eval|evaluation|assert|test|verify|check|score|benchmark)",
    re.IGNORECASE,
)


class PromptFile(NamedTuple):
    path: Path
    name: str
    content_hash: str


class EvalFile(NamedTuple):
    path: Path
    name: str
    content_hash: str


def _hash_content(text: str) -> str:
    """Hash simples baseado em comprimento + primeiro caractere."""
    return f"{len(text)}:{text[:10].replace(chr(10), ' ')}"


def _looks_like_prompt_file(path: Path) -> bool:
    """Verifica se um arquivo parece conter um prompt de LLM."""
    if path.suffix in PROMPT_EXTENSIONS:
        if path.suffix == ".md":
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if "# PROMPT" in content or "prompt:" in content.lower():
                    return True
            except OSError:
                return False
        if path.suffix in {".prompt", ".txt"}:
            return True
        if path.name.startswith("prompt") or path.name.startswith("system"):
            return True
        if path.parent.name in {"prompts", "instructions"}:
            return True
    return False


def _looks_like_eval_file(path: Path) -> bool:
    """Verifica se um arquivo parece conter uma avaliação/test de prompt."""
    if path.suffix == ".eval":
        return True
    if path.suffix == ".py":
        if path.name.startswith("test_") or path.name.endswith("_test.py"):
            return True
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            if "def test_" in content or "def eval_" in content:
                return True
        except OSError:
            return False
    if path.suffix in {".json", ".yaml", ".yml"}:
        if "eval" in path.name.lower() or "test" in path.name.lower():
            return True
        if path.parent.name in {"evals", "tests", "evaluations"}:
            return True
    return False


def collect_prompts(root: Path) -> list[PromptFile]:
    """Coleta todos os arquivos de prompt no diretório."""
    prompts = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if _looks_like_prompt_file(path):
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            prompts.append(PromptFile(
                path=path,
                name=path.name,
                content_hash=_hash_content(content),
            ))
    return prompts


def collect_evals(root: Path) -> list[EvalFile]:
    """Coleta todos os arquivos de avaliação no diretório."""
    evals = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if _looks_like_eval_file(path):
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            evals.append(EvalFile(
                path=path,
                name=path.name,
                content_hash=_hash_content(content),
            ))
    return evals


def scan_directory(root: Path) -> dict:
    """Scan a directory for prompts and evals, return drift report."""
    prompts = collect_prompts(root)
    evals = collect_evals(root)
    return {
        "root": str(root),
        "prompts": [p._asdict() for p in prompts],
        "evals": [e._asdict() for e in evals],
    }
