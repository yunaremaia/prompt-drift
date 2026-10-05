# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.1.1] - 2026-10-05

### Added

- `ruff.toml` pinning the `F` (pyflakes) rule set for `py310`, and a
  `python -m ruff check .` step in CI, so unused imports and unused locals
  cannot be merged again.
- Regression tests covering prompt/eval pairing, the drift count, and the
  `--json` contract.

### Changed

- `potential_drift` is now advisory: it is still reported, but it no longer
  counts toward `drift_count`, so a correctly paired project exits `0` instead
  of failing CI forever.
- `--json` routes all human-readable output to stderr, leaving stdout with only
  the JSON document.

### Fixed

- `_prompt_eval_match` no longer treats any two files as related. It matched on
  a shared parent directory, but `Path.parents` walks up to `/`, whose `.name`
  is `''`, so every prompt matched every eval and the `unEval'd_prompt` finding
  was unreachable.
- `drift_count` now counts every finding except the advisory
  `potential_drift`. It was recomputed from an allowlist that omitted
  `orphan_eval` and `orphan_prompt`, so a report holding findings still printed
  "No drift detected" and exited `0`.
- Two assertions in `tests/test_prompt_drift.py` that could never fail
  (`report.drift_count >= 0` and `len(report.findings) > 0 or
  report.drift_count >= 0`) now assert the behaviour they describe.
- Removed an unused local pair (`prompt_names`, `eval_names`) and an unused
  `scan_directory` import.
- `prompt_drift.__version__` was left at `0.1.0` while `pyproject.toml`
  declared `0.1.1`, so `prompt_drift.__version__` disagreed with the installed
  distribution metadata. It now reads `0.1.1`.
- `README.md` documented a `[tool.prompt-drift]` block in `pyproject.toml` (or
  `.prompt-drift.toml`) that no code ever read, claimed AST-based prompt
  extraction and YAML/JSON eval parsing that does not exist, and listed
  intent-drift / coverage-gap / stale-eval / behavioral-shift checks under a
  scanner that only pairs files by filename stem. The README now documents the
  four findings the tool actually emits and states that config support is not
  implemented.

## [0.1.0] - 2026-10-03

### Fixed

- Replaced the fail-open CI test gate (`pytest ... || echo "No tests directory
  found"`) and added tests that prove the gate bites.

## [Initial Release]

- Initial project release
