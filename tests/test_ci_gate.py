"""Guard the CI test gate against failing open.

`.github/workflows/python-tests.yml` used to run its test step as:

    pytest tests/ -v 2>/dev/null || echo "No tests directory found"

The `||` swallows the pytest exit status, so any failing test — or a
collection error, or a missing pytest — produced a green job and the
fallback message. The badge was reporting success over a suite that was
never run.

These tests read the workflow as text (no YAML dependency) and, most
importantly, execute the extracted test command so the gate is proven to
bite rather than merely inspected.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Operators that turn a non-zero exit status into a zero one.
FAIL_OPEN_OPERATORS = re.compile(r"\|\|\s*(echo\b|true\b|:|exit\s+0\b)")

# A step is a test step if its command mentions pytest.
TEST_COMMAND = re.compile(r"\bpython\b[^\n|]*-m\s+pytest|\bpytest\b")


def _workflow_files() -> list[Path]:
    files = sorted(
        p
        for p in WORKFLOW_DIR.glob("*.y*ml")
        if ".github" in p.parts
    )
    assert files, f"no workflow files found under {WORKFLOW_DIR}"
    return files


def _run_lines(path: Path) -> list[tuple[int, str]]:
    """Return (1-based line number, command) for every `run:` step.

    Handles both the inline form (`- run: pytest tests/`) and the block form
    (`- run: |` followed by an indented script), which is how the test step is
    normally written.
    """
    lines = path.read_text().splitlines()
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        # `run:` appears either as `- run: cmd` or as a sibling key of `- name:`.
        candidate = stripped[2:] if stripped.startswith("- ") else stripped
        if not (candidate == "run" or candidate.startswith("run:")):
            index += 1
            continue
        inline = candidate[len("run:") :].strip()
        if inline in ("|", ">", "|-", ">-"):
            # Block scalar: the body is every following line indented deeper
            # than the `run:` key itself. Bounding by indentation stops the
            # reader at the next step, which is at the same or lower level.
            key_indent = len(lines[index]) - len(lines[index].lstrip())
            body: list[str] = []
            cursor = index + 1
            while cursor < len(lines):
                line = lines[cursor]
                if not line.strip():
                    body.append("")
                    cursor += 1
                    continue
                indent = len(line) - len(line.lstrip())
                if indent <= key_indent:
                    break
                body.append(line.strip())
                cursor += 1
            found.append((index + 1, " ".join(part for part in body if part)))
            index = cursor
            continue
        found.append((index + 1, inline))
        index += 1
    return found


def _test_commands() -> list[tuple[Path, int, str]]:
    commands = []
    for path in _workflow_files():
        for lineno, command in _run_lines(path):
            if TEST_COMMAND.search(command):
                commands.append((path, lineno, command))
    return commands


class TestWorkflowTestStepsExist:
    def test_some_workflow_runs_the_test_suite(self):
        commands = _test_commands()
        assert commands, (
            "no workflow step invokes pytest — the test suite is not enforced "
            "by CI at all"
        )


class TestGateCannotFailOpen:
    def test_no_test_step_uses_a_fail_open_operator(self):
        offenders = []
        for path, lineno, command in _test_commands():
            match = FAIL_OPEN_OPERATORS.search(command)
            if match:
                offenders.append(
                    f"{path.relative_to(REPO_ROOT)}:{lineno}: "
                    f"`{match.group(0)}` makes the step exit 0 even when "
                    f"pytest fails\n    {command}"
                )
        assert not offenders, (
            "CI test steps swallow pytest's exit status, so a failing suite "
            "reports green:\n" + "\n".join(offenders)
        )

    def test_no_test_step_discards_stderr(self):
        offenders = []
        for path, lineno, command in _test_commands():
            if "2>/dev/null" in command:
                offenders.append(
                    f"{path.relative_to(REPO_ROOT)}:{lineno}: stderr is "
                    f"discarded, hiding collection and import errors\n"
                    f"    {command}"
                )
        assert not offenders, (
            "CI test steps redirect stderr to /dev/null, so the failure "
            "output that would explain a red job is never printed:\n"
            + "\n".join(offenders)
        )


class TestTestDependenciesAreDeclared:
    def test_the_dev_extra_the_workflow_installs_exists(self):
        """`pip install -e ".[dev]"` must not be a no-op.

        pip only warns about an unknown extra and still exits 0, so a
        missing `[project.optional-dependencies]` section means the test
        dependencies are never installed from this project at all.
        """
        workflow_text = "\n".join(p.read_text() for p in _workflow_files())
        extras = set(re.findall(r"\"\.\[([A-Za-z0-9_.-]+)\]\"", workflow_text))
        assert extras, "no workflow installs an optional dependency group"

        pyproject = PYPROJECT.read_text()
        declared = set(re.findall(r"^\s*([A-Za-z0-9_.-]+)\s*=\s*\[", pyproject, re.M))
        # Anything under [project.optional-dependencies] or [project.optional-dev-dependencies]
        optional_block = re.search(
            r"\[project\.optional(?:-dev)?-dependencies\](.*?)(?=\n\[|\Z)",
            pyproject,
            re.S,
        )
        if optional_block:
            declared |= set(
                re.findall(r"^\s*([A-Za-z0-9_.-]+)\s*=\s*\[", optional_block.group(1), re.M)
            )

        missing = extras - declared
        assert not missing, (
            f"workflow installs extras {sorted(extras)} but pyproject.toml "
            f"declares {sorted(declared)}; missing {sorted(missing)}. pip only "
            f"warns for an unknown extra, so the test dependencies are never "
            f"installed."
        )

    def test_pytest_is_declared_as_a_test_dependency(self):
        pyproject = PYPROJECT.read_text()
        assert re.search(r"pytest", pyproject), (
            "pytest is not declared anywhere in pyproject.toml, so CI relies "
            "on whatever pytest the runner image happens to ship"
        )


def _run_gate(command: str, workdir: Path) -> subprocess.CompletedProcess:
    """Execute a workflow test command against `workdir`.

    Whatever interpreter spelling the workflow uses (`pytest ...` or
    `python -m pytest ...`) is rewritten to *this* interpreter's `-m pytest`,
    so the result reflects the command's exit-status handling rather than
    which pytest happens to be first on PATH. `python` is used as the
    replacement rather than an absolute path because the probe runs inside a
    throwaway temp tree with no virtualenv of its own.
    """
    # A single pass, so the `pytest` inside an already-rewritten
    # "python -m pytest" is not rewritten a second time. The replacement is
    # this interpreter's absolute path: bare `python` inside the temp tree can
    # resolve to an unrelated interpreter that has no pytest installed, which
    # would report a broken gate for the wrong reason.
    interpreter = json.dumps(sys.executable)
    translated = re.sub(
        r"\bpython(?:3(?:\.\d+)?)?\b[^\n]*?-m\s+pytest\b|(?<![\w./-])pytest\b",
        f"{interpreter} -m pytest",
        command,
    )
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        ["bash", "-c", translated],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )


class TestGateActuallyBites:
    def _each_workflow_command(self):
        for path, lineno, command in _test_commands():
            yield path, lineno, command

    def test_gate_fails_when_a_test_fails(self, tmp_path: Path):
        """The decisive check: the real workflow command must exit non-zero.

        A failing test is dropped into the layout the command expects and the
        command is executed verbatim. If the gate fails open this returns 0.
        """
        checked = 0
        for path, lineno, command in self._each_workflow_command():
            tests_dir = tmp_path / "tests"
            tests_dir.mkdir(parents=True, exist_ok=True)
            (tests_dir / "test_ci_gate_probe.py").write_text(
                "def test_deliberately_fails():\n"
                "    assert False, 'this test must make the CI gate exit non-zero'\n"
            )
            result = _run_gate(command, tmp_path)
            checked += 1
            assert result.returncode != 0, (
                f"{path.relative_to(REPO_ROOT)}:{lineno} exited 0 despite a "
                f"failing test — the CI gate fails open:\n"
                f"    {command}\n"
                f"    stdout: {result.stdout[-500:]}\n"
                f"    stderr: {result.stderr[-500:]}"
            )
        assert checked, "no workflow test command was exercised"

    def test_gate_passes_when_all_tests_pass(self, tmp_path: Path):
        """The gate must still be able to go green, or it is not a gate."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_ci_gate_probe.py").write_text(
            "def test_passes():\n    assert True\n"
        )
        for path, lineno, command in self._each_workflow_command():
            result = _run_gate(command, tmp_path)
            assert result.returncode == 0, (
                f"{path.relative_to(REPO_ROOT)}:{lineno} exited "
                f"{result.returncode} on a passing suite — the gate is broken "
                f"in the other direction:\n"
                f"    {command}\n"
                f"    stderr: {result.stderr[-500:]}"
            )

    def test_gate_fails_when_the_suite_cannot_be_collected(self, tmp_path: Path):
        """A collection error must redden CI, not print 'No tests found'."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_broken_import.py").write_text(
            "import a_module_that_does_not_exist_anywhere\n"
        )
        for path, lineno, command in self._each_workflow_command():
            result = _run_gate(command, tmp_path)
            assert result.returncode != 0, (
                f"{path.relative_to(REPO_ROOT)}:{lineno} exited 0 on an "
                f"uncollectable suite — import errors are invisible to CI:\n"
                f"    {command}\n"
                f"    stdout: {result.stdout[-500:]}"
            )