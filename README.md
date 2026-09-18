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

## Project Links

- Repository: https://github.com/yunaremaia/prompt-drift
- Issues: https://github.com/yunaremaia/prompt-drift/issues
