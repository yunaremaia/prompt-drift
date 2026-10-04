"""Regression tests for the four defects fixed in 0.1.1.

Each test below reproduces a bug that shipped with a green suite, so each one
names the failure mode it locks down rather than just exercising a code path.

- #12  ``_prompt_eval_match`` treated any two files as related because
       ``Path.parents`` walks up to ``/``, whose ``.name`` is ``''``. Every
       prompt matched every eval, so ``matching_evals`` was never empty and the
       ``unEval'd_prompt`` finding was unreachable dead code.
- #17  Every matched pair emitted ``potential_drift`` and ``potential_drift``
       fed ``drift_count``, so a correctly paired project exited 1 forever.
- #18  ``--json`` wrote rich's human-readable lines to stdout ahead of the
       document, so ``prompt-drift ./p --json | jq .`` never parsed.
- #19  ``drift_count`` was recomputed from an allowlist that omitted
       ``orphan_eval``/``orphan_prompt``, so a directory with findings still
       printed "No drift detected" and exited 0.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from prompt_drift.detectors import _prompt_eval_match, detect_drift
from prompt_drift.scanner import collect_evals, collect_prompts

ADVISORY = "potential_drift"


def _paired_project(root: Path) -> None:
    """A project whose prompt and eval are correctly paired by name."""
    (root / "prompts").mkdir()
    (root / "evals").mkdir()
    (root / "prompts" / "summarizer.prompt").write_text(
        "Summarize the document in three bullet points.", encoding="utf-8"
    )
    (root / "evals" / "test_summarizer.py").write_text(
        "def test_summarizer():\n    assert True\n", encoding="utf-8"
    )


def _drift(root: Path):
    return detect_drift(collect_prompts(root), collect_evals(root), root)


class TestPromptWithoutEval:
    """#12 / #17: a prompt nothing evaluates must be the headline finding."""

    def test_lone_prompt_yields_high_severity_finding_and_exit_one(self, tmp_path: Path):
        prompts = tmp_path / "prompts"
        prompts.mkdir()
        (prompts / "chat_system.prompt").write_text("You are helpful.", encoding="utf-8")

        report = _drift(tmp_path)

        high = [f for f in report.findings if f.drift_type == "unEval'd_prompt"]
        assert len(high) == 1, (
            "a prompt with no eval at all must produce exactly one "
            f"unEval'd_prompt finding, got {report.findings!r}"
        )
        assert high[0].severity == "high"
        assert report.drift_count >= 1
        assert report.exit_code == 1

    def test_prompt_unmatched_by_an_unrelated_eval_is_still_flagged(self, tmp_path: Path):
        """The #12 case: an eval exists, it just belongs to a different prompt.

        Before the fix ``_prompt_eval_match`` returned True here, the prompt
        looked evaluated, and no finding was emitted at all.
        """
        (tmp_path / "prompts").mkdir()
        (tmp_path / "evals").mkdir()
        (tmp_path / "prompts" / "chat_system.prompt").write_text(
            "You are helpful.", encoding="utf-8"
        )
        (tmp_path / "evals" / "test_billing_totals.py").write_text(
            "def test_billing_totals():\n    assert True\n", encoding="utf-8"
        )

        report = _drift(tmp_path)

        types = [f.drift_type for f in report.findings]
        assert "unEval'd_prompt" in types, (
            "an eval for a different prompt must not make this prompt look "
            f"evaluated; got {types}"
        )
        assert report.drift_count >= 1
        assert report.exit_code == 1


class TestEvalWithoutPrompt:
    """#19: findings that only reached the report were never counted."""

    def test_lone_eval_is_reported_and_exits_one(self, tmp_path: Path):
        evals = tmp_path / "evals"
        evals.mkdir()
        (evals / "test_billing_totals.py").write_text(
            "def test_billing_totals():\n    assert True\n", encoding="utf-8"
        )

        report = _drift(tmp_path)

        assert report.findings, "an eval with no prompt must produce a finding"
        assert {f.drift_type for f in report.findings} <= {"orphan_eval", "orphan_prompt"}
        assert report.drift_count >= 1, (
            "orphan findings must count toward drift_count — otherwise the "
            f"report has findings but exits 0 (got drift_count="
            f"{report.drift_count})"
        )
        assert report.exit_code == 1

    def test_every_finding_type_counts_except_the_advisory_one(self, tmp_path: Path):
        (tmp_path / "prompts").mkdir()
        (tmp_path / "evals").mkdir()
        (tmp_path / "prompts" / "chat_system.prompt").write_text("Hi.", encoding="utf-8")
        (tmp_path / "evals" / "test_billing_totals.py").write_text(
            "def test_billing_totals():\n    assert True\n", encoding="utf-8"
        )

        report = _drift(tmp_path)

        actionable = [f for f in report.findings if f.drift_type != ADVISORY]
        assert report.drift_count == len(actionable), (
            "drift_count must count every non-advisory finding, including the "
            f"low-severity orphans (drift_count={report.drift_count}, "
            f"findings={[f.drift_type for f in report.findings]})"
        )
        assert report.exit_code == 1


class TestCorrectlyPairedProjectIsGreen:
    """#17: this is the control that matters — a synced project must pass CI."""

    def test_matched_pair_exits_zero(self, tmp_path: Path):
        _paired_project(tmp_path)

        report = _drift(tmp_path)

        assert report.exit_code == 0, (
            "a correctly paired project must exit 0; an always-red gate gets "
            f"ignored or disabled. findings={[f.drift_type for f in report.findings]}"
        )
        assert report.drift_count == 0

    def test_potential_drift_is_still_reported_for_a_human_reviewer(self, tmp_path: Path):
        """Excluding it from drift_count must not delete it from the report.

        The finding is real information; only its contribution to the exit
        code is what changed. Dropping it silently would lose the signal
        without fixing the gate.
        """
        _paired_project(tmp_path)

        report = _drift(tmp_path)

        assert [f.drift_type for f in report.findings] == [ADVISORY]
        assert report.drift_count == 0, "an advisory finding must not redden CI"
        assert report.exit_code == 0


class TestPromptEvalMatching:
    """#12: stem-based matching only — no shared-ancestor clause."""

    def test_unrelated_names_do_not_match(self):
        assert _prompt_eval_match(
            Path("/x/prompts/chat_system.md"), Path("/y/evals/test_billing_totals.py")
        ) is False

    def test_a_shared_ancestor_directory_does_not_match(self):
        """The exact defect: both paths reach ``/``, whose name is ``''``."""
        assert _prompt_eval_match(
            Path("/anything/aaa/prompts/alpha.md"), Path("/anything/zzz/evals/omega.py")
        ) is False

    def test_stem_convention_still_matches(self):
        """The real convention keeps working: ``summarizer`` in ``test_summarizer``."""
        assert _prompt_eval_match(
            Path("/x/prompts/summarizer.prompt"), Path("/y/evals/test_summarizer.py")
        ) is True

    def test_identical_stem_matches(self):
        assert _prompt_eval_match(
            Path("/x/prompts/chat_system.md"), Path("/y/evals/chat_system.eval")
        ) is True

    def test_real_project_pairing_survives_the_fix(self, tmp_path: Path):
        """Positive control: the fix must not deny every match in a real scan."""
        _paired_project(tmp_path)

        prompts = collect_prompts(tmp_path)
        evals = collect_evals(tmp_path)
        assert len(prompts) == 1 and len(evals) == 1
        assert _prompt_eval_match(prompts[0].path, evals[0].path) is True


class TestJsonOutputIsParseable:
    """#18: stdout carries the document, and only the document."""

    def _run(self, root: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "prompt_drift.cli", str(root), "--json"],
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_stdout_parses_with_json_load(self, tmp_path: Path):
        _paired_project(tmp_path)

        result = self._run(tmp_path)

        assert result.returncode == 0, result.stderr
        document = json.loads(result.stdout)
        assert document["root"] == str(tmp_path.resolve())
        assert document["prompts"] == 1
        assert document["evals"] == 1
        assert document["exit_code"] == 0
        assert isinstance(document["findings"], list)

    def test_human_output_is_not_mixed_into_stdout(self, tmp_path: Path):
        """``--no-progress`` alone never fixed this: the "Scanning" line was
        printed unconditionally before the flag was consulted."""
        _paired_project(tmp_path)

        result = self._run(tmp_path)

        assert not result.stdout.startswith("Scanning"), (
            "rich output leaked onto stdout ahead of the JSON document:\n"
            f"{result.stdout[:300]}"
        )
        assert "Scanning" in result.stderr, (
            f"human-readable output should move to stderr, not vanish:\n"
            f"stderr={result.stderr[:300]!r}"
        )

    def test_json_reports_findings_and_a_nonzero_exit(self, tmp_path: Path):
        """The finding list and the exit code must agree, in JSON too."""
        evals = tmp_path / "evals"
        evals.mkdir()
        (evals / "test_billing_totals.py").write_text(
            "def test_billing_totals():\n    assert True\n", encoding="utf-8"
        )

        result = self._run(tmp_path)

        document = json.loads(result.stdout)
        assert result.returncode == 1, result.stderr
        assert document["exit_code"] == 1
        assert document["drift_count"] >= 1
        assert document["findings"], "the JSON document must carry the findings"
