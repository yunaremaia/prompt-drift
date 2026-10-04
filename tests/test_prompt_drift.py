"""Testes para prompt-drift."""

from pathlib import Path

from prompt_drift.scanner import collect_prompts, collect_evals
from prompt_drift.detectors import detect_drift, DriftReport


class TestCollectPrompts:
    """Testes para coleta de arquivos de prompt."""

    def test_collects_prompt_files(self, tmp_path: Path):
        """Arquivos .prompt são coletados."""
        (tmp_path / "system.prompt").write_text("You are a helpful assistant.")
        prompts = collect_prompts(tmp_path)
        assert len(prompts) == 1
        assert prompts[0].name == "system.prompt"

    def test_collects_txt_prompt_files(self, tmp_path: Path):
        """Arquivos .txt com conteúdo de prompt são coletados."""
        (tmp_path / "instruction.txt").write_text("Respond in JSON format.")
        prompts = collect_prompts(tmp_path)
        assert len(prompts) == 1

    def test_collects_md_with_prompt_marker(self, tmp_path: Path):
        """Markdown com # PROMPT é coletado."""
        (tmp_path / "README.md").write_text("# My Project\n\n# PROMPT\nYou are helpful.")
        prompts = collect_prompts(tmp_path)
        assert len(prompts) == 1

    def test_ignores_code_files(self, tmp_path: Path):
        """Arquivos de código sem markers de prompt são ignorados."""
        (tmp_path / "main.py").write_text("print('hello')")
        prompts = collect_prompts(tmp_path)
        assert len(prompts) == 0

    def test_empty_directory(self, tmp_path: Path):
        """Diretório vazio retorna lista vazia."""
        prompts = collect_prompts(tmp_path)
        assert prompts == []

    def test_nested_prompt_files(self, tmp_path: Path):
        """Arquivos em subdiretórios são coletados."""
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "prompt.txt").write_text("Test prompt.")
        prompts = collect_prompts(tmp_path)
        assert len(prompts) == 1


class TestCollectEvals:
    """Testes para coleta de arquivos de avaliação."""

    def test_collects_py_test_files(self, tmp_path: Path):
        """Arquivos Python com def test_ são coletados."""
        (tmp_path / "test_prompt.py").write_text(
            "def test_prompt():\n    assert True"
        )
        evals = collect_evals(tmp_path)
        assert len(evals) == 1
        assert evals[0].name == "test_prompt.py"

    def test_collects_eval_files(self, tmp_path: Path):
        """Arquivos .eval são coletados."""
        (tmp_path / "eval.eval").write_text('{"test": "value"}')
        evals = collect_evals(tmp_path)
        assert len(evals) == 1

    def test_empty_directory(self, tmp_path: Path):
        """Diretório vazio retorna lista vazia."""
        evals = collect_evals(tmp_path)
        assert evals == []


class TestDetectDrift:
    """Testes para detecção de drift."""

    def test_no_drift_when_empty(self):
        """Sem prompts ou evals, não há drift."""
        report = detect_drift([], [])
        assert report.drift_count == 0
        assert report.exit_code == 0

    def test_flag_un_evaluated_prompt(self, tmp_path: Path):
        """Prompt sem avaliação correspondente é flaggeado."""
        (tmp_path / "system.prompt").write_text("You are helpful.")
        prompts = collect_prompts(tmp_path)
        evals = collect_evals(tmp_path)
        report = detect_drift(prompts, evals, tmp_path)
        assert report.drift_count == 1
        assert [f.drift_type for f in report.findings] == ["unEval'd_prompt"]

    def test_flag_orphan_eval(self, tmp_path: Path):
        """Eval sem prompt correspondente é flaggeado.

        The old assertion here was ``report.drift_count >= 0``, which cannot
        fail. This one requires the finding to be counted, not merely present.
        """
        (tmp_path / "test_eval.py").write_text("def test_eval(): pass")
        evals = collect_evals(tmp_path)
        prompts = collect_prompts(tmp_path)
        report = detect_drift(prompts, evals, tmp_path)
        assert "orphan_eval" in [f.drift_type for f in report.findings]
        assert report.drift_count == 1
        assert report.exit_code == 1

    def test_exit_code_on_drift(self, tmp_path: Path):
        """Exit code 1 quando drift é detectado."""
        (tmp_path / "system.prompt").write_text("Test.")
        prompts = collect_prompts(tmp_path)
        evals = collect_evals(tmp_path)
        report = detect_drift(prompts, evals, tmp_path)
        assert report.exit_code == 1


class TestDriftReport:
    """Testes para DriftReport."""

    def test_bool_true_when_drift(self):
        """DriftReport é truthy quando drift_count > 0."""
        report = DriftReport(drift_count=1)
        assert bool(report) is True

    def test_bool_false_when_no_drift(self):
        """DriftReport é falsy quando drift_count == 0."""
        report = DriftReport(drift_count=0)
        assert bool(report) is False

    def test_exit_code_matches_drift_count(self):
        """Exit code 1 quando drift_count > 0."""
        report = DriftReport(drift_count=3)
        assert report.exit_code == 1

    def test_exit_code_zero_when_no_drift(self):
        """Exit code 0 quando drift_count == 0."""
        report = DriftReport(drift_count=0)
        assert report.exit_code == 0


class TestPromptEvalMatching:
    """Testes para correspondência prompt-eval."""

    def test_same_name_match(self, tmp_path: Path):
        """Arquivos com mesmo nome base são considerados relacionados.

        The old assertion here was
        ``len(report.findings) > 0 or report.drift_count >= 0``, whose second
        branch is always true, so the test could never fail — and the fixture
        it used did not even produce a pair: ``system_eval.py`` is not
        collected as an eval (the scanner looks for ``def test_``, not
        ``def test``), so there was nothing to match against.

        This asserts what the docstring claims: a matched pair produces no
        orphan finding and keeps the gate green.
        """
        (tmp_path / "system.prompt").write_text("Test.")
        (tmp_path / "system.eval").write_text('{"test": "value"}')
        prompts = collect_prompts(tmp_path)
        evals = collect_evals(tmp_path)
        report = detect_drift(prompts, evals, tmp_path)
        # system.prompt e system.eval têm o mesmo nome base
        assert len(prompts) == 1 and len(evals) == 1
        orphan_types = {"orphan_eval", "orphan_prompt", "unEval'd_prompt"}
        assert not orphan_types & {f.drift_type for f in report.findings}
        assert report.exit_code == 0
