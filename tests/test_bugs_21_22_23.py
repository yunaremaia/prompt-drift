"""Regression tests for bugs #21, #22, #23."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from prompt_drift.detectors import detect_drift
from prompt_drift.scanner import _looks_like_prompt_file, collect_evals, collect_prompts


# ── Bug #21: text renderer branches on drift_count while JSON branches on findings ──

class TestBug21_TextRendererBranchesOnFindings:
    """A report holding findings must never print 'No drift detected'."""

    def test_text_renderer_does_not_claim_no_drift_when_findings_exist(self, tmp_path: Path):
        """Advisory findings (drift_count==0) must not print 'No drift detected'."""
        (tmp_path / "prompts").mkdir()
        (tmp_path / "evals").mkdir()
        (tmp_path / "prompts" / "summarizer.prompt").write_text("Summarize.")
        (tmp_path / "evals" / "test_summarizer.py").write_text("def test_summarizer(): pass")

        result = subprocess.run(
            [sys.executable, "-m", "prompt_drift.cli", str(tmp_path)],
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0
        assert "No drift detected" not in result.stdout, (
            f"text renderer must not claim 'No drift detected' when findings exist:\n{result.stdout}"
        )
        assert "all in sync" not in result.stdout

    def test_text_renderer_shows_advisory_findings(self, tmp_path: Path):
        """Advisory findings should be visible in text output."""
        (tmp_path / "prompts").mkdir()
        (tmp_path / "evals").mkdir()
        (tmp_path / "prompts" / "summarizer.prompt").write_text("Summarize.")
        (tmp_path / "evals" / "test_summarizer.py").write_text("def test_summarizer(): pass")

        result = subprocess.run(
            [sys.executable, "-m", "prompt_drift.cli", str(tmp_path)],
            capture_output=True, text=True, timeout=120,
        )
        assert "potential_drift" in result.stdout or "advisory" in result.stdout.lower()

    def test_text_renderer_prints_no_drift_when_truly_empty(self, tmp_path: Path):
        """A report with zero findings should still print 'No drift detected'."""
        result = subprocess.run(
            [sys.executable, "-m", "prompt_drift.cli", str(tmp_path)],
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0
        assert "No drift detected" in result.stdout


# ── Bug #22: every .txt file is classified as an LLM prompt ──

class TestBug22_TxtFilesNeedContentCheck:
    """Non-prompt .txt files must not be classified as prompts."""

    def test_plain_txt_is_not_a_prompt(self, tmp_path: Path):
        """requirements.txt with no prompt markers is not a prompt."""
        (tmp_path / "requirements.txt").write_text("click>=8.0\nrich>=13.0\n")
        assert _looks_like_prompt_file(tmp_path / "requirements.txt") is False

    def test_license_txt_is_not_a_prompt(self, tmp_path: Path):
        """LICENSE.txt is not a prompt."""
        (tmp_path / "LICENSE.txt").write_text("MIT License\n\nPermission is hereby...")
        assert _looks_like_prompt_file(tmp_path / "LICENSE.txt") is False

    def test_notes_txt_is_not_a_prompt(self, tmp_path: Path):
        """A notes file is not a prompt."""
        (tmp_path / "notes.txt").write_text("shopping list\n- milk\n")
        assert _looks_like_prompt_file(tmp_path / "notes.txt") is False

    def test_txt_with_prompt_marker_is_a_prompt(self, tmp_path: Path):
        """A .txt file containing prompt markers IS a prompt."""
        (tmp_path / "instruction.txt").write_text("prompt: You are a helpful assistant.")
        assert _looks_like_prompt_file(tmp_path / "instruction.txt") is True

    def test_prompt_extension_is_unconditional(self, tmp_path: Path):
        """.prompt extension needs no content check."""
        (tmp_path / "anything.prompt").write_text("random content")
        assert _looks_like_prompt_file(tmp_path / "anything.prompt") is True

    def test_repo_with_no_prompts_exits_zero(self, tmp_path: Path):
        """A repo with only non-prompt .txt files should report 0 prompts and exit 0."""
        (tmp_path / "requirements.txt").write_text("click>=8.0\n")
        (tmp_path / "LICENSE.txt").write_text("MIT License\n")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("def main(): pass\n")

        result = subprocess.run(
            [sys.executable, "-m", "prompt_drift.cli", str(tmp_path)],
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, (
            f"repo with no prompts must exit 0, got {result.returncode}\n{result.stdout}"
        )
        assert "0 prompts" in result.stdout


# ── Bug #23: detect_drift's 'similar name' fallback re-tests the predicate it just rejected ──

class TestBug23_SimilarNameFallback:
    """The fallback must use a different, looser match than _prompt_eval_match."""

    def test_renamed_eval_produces_orphan_eval_not_uneval_prompt(self, tmp_path: Path):
        """A prompt whose eval was renamed should produce orphan_eval, not unEval'd_prompt."""
        (tmp_path / "prompts").mkdir()
        (tmp_path / "evals").mkdir()
        (tmp_path / "prompts" / "summarize_doc.prompt").write_text("Summarize the document.")
        (tmp_path / "evals" / "test_doc.py").write_text("def test_doc(): pass")

        report = detect_drift(collect_prompts(tmp_path), collect_evals(tmp_path), tmp_path)
        types = [f.drift_type for f in report.findings]
        assert "unEval'd_prompt" not in types, (
            f"renamed eval must not produce unEval'd_prompt; got {types}"
        )
        assert "orphan_eval" in types, (
            f"renamed eval should produce orphan_eval; got {types}"
        )

    def test_renamed_prompt_produces_orphan_prompt(self, tmp_path: Path):
        """An eval whose prompt was renamed should produce orphan_prompt."""
        (tmp_path / "prompts").mkdir()
        (tmp_path / "evals").mkdir()
        (tmp_path / "prompts" / "translate_doc.prompt").write_text("Translate the document.")
        (tmp_path / "evals" / "test_doc.py").write_text("def test_doc(): pass")

        report = detect_drift(collect_prompts(tmp_path), collect_evals(tmp_path), tmp_path)
        types = [f.drift_type for f in report.findings]
        assert "orphan_prompt" in types, (
            f"renamed prompt should produce orphan_prompt; got {types}"
        )

    def test_truly_unrelated_files_still_produce_uneval_prompt(self, tmp_path: Path):
        """Completely unrelated names should still produce unEval'd_prompt."""
        (tmp_path / "prompts").mkdir()
        (tmp_path / "evals").mkdir()
        (tmp_path / "prompts" / "alpha.prompt").write_text("Alpha.")
        (tmp_path / "evals" / "test_omega.py").write_text("def test_omega(): pass")

        report = detect_drift(collect_prompts(tmp_path), collect_evals(tmp_path), tmp_path)
        types = [f.drift_type for f in report.findings]
        assert "unEval'd_prompt" in types, (
            f"unrelated names must produce unEval'd_prompt; got {types}"
        )
