# prompt-drift

Detect drift between LLM prompts and their evaluation tests — when prompts change but evals don't.

## Problem

LLM applications evolve rapidly. Prompts are edited, refined, and A/B tested — but the evaluation suites that validate prompt quality often lag behind. This creates a silent failure mode:

- **Prompt updated** to handle a new edge case, but evals still test the old behavior
- **Eval set expanded** with new test cases that the current prompt fails
- **Prompt intent shifted** (e.g., from concise to explanatory) but success criteria unchanged
- **Regression undetected** because stale evals pass while real-world quality degrades

Existing evals frameworks (`promptfoo`, `evals`, `langsmith`) *run* tests — they don't detect structural drift between prompts and their test suites.

## Solution

`prompt-drift` analyzes the relationship between prompts and their evaluation files to detect:

Detection is structural: prompts and evals are paired by filename stem
(`prompts/summarizer.prompt` ↔ `evals/test_summarizer.py`) and the pairing is
reported when it is broken.

| Finding | Severity | What it catches |
|---------|----------|----------------|
| `unEval'd_prompt` | high | Coverage gap — a prompt nothing evaluates |
| `orphan_eval` | low | An eval with no prompt, or possibly stale against a similarly named one |
| `orphan_prompt` | medium | A prompt whose eval may target outdated content |
| `potential_drift` | medium | Advisory only — a matched pair to verify by hand; does not fail CI |

Intent drift, stale evals and behavioral shift need semantic comparison of the
prompt against its eval, which is not implemented — see [Roadmap](#roadmap).

## Install

Not published on PyPI yet, so install it straight from the repository:

```bash
pip install git+https://github.com/yunaremaia/prompt-drift.git
```

Or from source:

```bash
git clone https://github.com/yunaremaia/prompt-drift.git
cd prompt-drift
pip install -e .
```

### Usage

The path to scan is a positional argument; there is no `scan` subcommand.

```bash
# Scan a project for prompt-eval drift (defaults to the current directory)
prompt-drift ./my-project

# JSON output for CI — stdout carries only the JSON document
prompt-drift ./my-project --json

# Suppress the "Found N prompts, M evals" line
prompt-drift ./my-project --no-progress
```

There is no config file. Prompts and evals are discovered by extension and
directory convention (`.prompt`/`.txt`, plus `# PROMPT` markers in Markdown;
`test_*.py`, `.eval`, and `eval`/`test` files under `evals/`), so no
`pyproject.toml` or `.prompt-drift.toml` entry is read today.

SARIF output is on the [roadmap](#roadmap), not implemented yet.

### Exit Codes

- `0` — no drift detected (`potential_drift` alone still exits `0`)
- `1` — drift detected (CI fail)
- `2` — invalid path argument

## Stack

- **Language:** Python 3.10+
- **Discovery:** Filename/extension convention — no AST, YAML or JSON parsing
- **Output:** Terminal, JSON (SARIF planned)
- **Tests:** `pytest`

## Roadmap

- [x] Core scanner: pair prompts and evals by filename stem, flag broken pairs
- [x] Terminal and `--json` output with CI exit codes
- [ ] Config-driven prompt-eval mapping (`[tool.prompt-drift]`)
- [ ] Semantic comparison: intent drift, stale evals, behavioral shift
- [ ] SARIF output for GitHub Advanced Security
- [ ] Auto-suggest new eval cases for changed prompts
- [ ] Git pre-commit hook integration
- [ ] Diff mode: compare two prompt versions
- [ ] Multi-format support (`.yaml`, `.json` prompts)

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

Please follow the existing test-first pattern and run `pytest` before submitting.

## License

MIT

## Relationship to driftcheck

[prompt-drift](https://github.com/yunaremaia/prompt-drift) é um complemento ao [driftcheck](https://github.com/yunaremaia/driftcheck):

| driftcheck | prompt-drift |
|------------|--------------|
| Drift de toolchain/config (Dockerfile vs README, rust-toolchain vs CI, etc.) | Drift entre prompts de LLM e seus testes de avaliação |
| 61+ detectores em 14+ ecossistemas | Focado: correspodência prompt/eval |
| Modo `--fix` para correção automática | Modo de revisão manual (prompts são semânticos, não auto-corrigíveis) |
| Exit 1 em qualquer drift | Exit 1 em findings de drift |

Ambos seguem a mesma filosofia: detectar drift entre o que algo _diz_ e o que algo _é_ — seja um README e um Dockerfile, ou um prompt de sistema e seu suite de testes.

## Badges

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![CI](https://github.com/yunaremaia/prompt-drift/actions/workflows/python-tests.yml/badge.svg)](https://github.com/yunaremaia/prompt-drift/actions/workflows/python-tests.yml)
