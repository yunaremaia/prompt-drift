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

| Check | What it catches |
|-------|----------------|
| Intent drift | Prompt behavior changed but eval criteria untouched |
| Coverage gap | New prompt capabilities with no corresponding eval |
| Stale evals | Test cases that no longer match prompt's stated behavior |
| Behavioral shift | Prompt tone/structure change not reflected in rubrics |

### Usage

```bash
# Scan a project for prompt-eval drift
prompt-drift scan

# Define prompt-eval relationships in config
# (in pyproject.toml or .prompt-drift.toml)
[tool.prompt-drift]
prompts = ["prompts/"]
evals = ["evals/", "tests/prompts/"]

# Run with config
prompt-drift scan --config .prompt-drift.toml

# Output formats
prompt-drift scan --format json   # CI-friendly
prompt-drift scan --format sarif  # GitHub Code Scanning integration
```

### Exit Codes

- `0` — no drift detected
- `1` — drift detected (CI fail)
- `2` — config error

## Stack

- **Language:** Python 3.11+
- **Parser:** AST-based prompt extraction, YAML/JSON eval parsing
- **Config:** `pyproject.toml` (PEP 621) or standalone `.prompt-drift.toml`
- **Output:** Terminal, JSON, SARIF
- **Tests:** `pytest`

## Roadmap

- [ ] Core scanner: intent/coverage/stale/behavioral checks
- [ ] Config-driven prompt-eval mapping
- [ ] SARIF output for GitHub Advanced Security
- [ ] Auto-suggest new eval cases for changed prompts
- [ ] Git pre-commit hook integration
- [ ] Diff mode: compare two prompt versions
- [ ] LLM-assisted drift detection (semantic similarity)
- [ ] Multi-format support (`.txt`, `.md`, `.yaml`, `.json` prompts)

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

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/tests-TBD-green?logo=pytest)
