"""Detecção de drift entre prompts e avaliações."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from prompt_drift.scanner import PromptFile, EvalFile

# Finding type that is reported but does not fail the gate. See the comment on
# the `drift_count` computation in `detect_drift` for the rationale.
ADVISORY_FINDING_TYPE = "potential_drift"


@dataclass
class DriftFinding:
    """Encontrada uma instância de drift entre prompt e avaliação."""
    prompt_path: Optional[Path] = None
    eval_path: Optional[Path] = None
    drift_type: str = ""
    severity: str = "medium"
    detail: str = ""


@dataclass
class DriftReport:
    """Relatório completo de drift detectado."""
    total_prompts: int = 0
    total_evals: int = 0
    drift_count: int = 0
    findings: list[DriftFinding] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return 1 if self.drift_count > 0 else 0

    def __bool__(self) -> bool:
        return self.drift_count > 0


def detect_drift(prompts: list[PromptFile], evals: list[EvalFile],
                 root: Optional[Path] = None) -> DriftReport:
    """Analisa prompts e avaliações para detectar drift.

    Drift é detectado quando:
    1. Um prompt existe sem avaliação correspondente
    2. Uma avaliação existe sem prompt correspondente
    3. Prompt e avaliação coexistem mas há indicação de desatualização

    Todos os findings entram em `report.findings` e, exceto o advisory
    `ADVISORY_FINDING_TYPE`, contribuem para `drift_count` — que é o que
    determina `exit_code`.
    """
    if root is None:
        root = Path.cwd()

    report = DriftReport(
        total_prompts=len(prompts),
        total_evals=len(evals),
    )

    if not prompts and not evals:
        return report

    # Prompts sem avaliação correspondente
    for prompt in prompts:
        matching_evals = [e for e in evals
                         if _prompt_eval_match(prompt.path, e.path)]
        if not matching_evals:
            # Tentar encontrar por nome similar
            similar = [e for e in evals
                      if _similar_names(prompt.path, e.path)]
            if similar:
                for eval_f in similar:
                    report.findings.append(DriftFinding(
                        prompt_path=prompt.path,
                        eval_path=eval_f.path,
                        drift_type="orphan_eval",
                        severity="low",
                        detail=f"Eval {eval_f.name} exists but may be stale relative to prompt {prompt.name}",
                    ))
            else:
                report.findings.append(DriftFinding(
                    prompt_path=prompt.path,
                    eval_path=None,
                    drift_type="unEval'd_prompt",
                    severity="high",
                    detail=f"Prompt {prompt.name} has no corresponding evaluation/test",
                ))

    # Avaliações sem prompt correspondente
    for eval_f in evals:
        matching_prompts = [p for p in prompts
                           if _prompt_eval_match(p.path, eval_f.path)]
        if not matching_prompts:
            similar = [p for p in prompts
                      if _similar_names(eval_f.path, p.path)]
            if similar:
                for prompt in similar:
                    report.findings.append(DriftFinding(
                        prompt_path=prompt.path,
                        eval_path=eval_f.path,
                        drift_type="orphan_prompt",
                        severity="medium",
                        detail=f"Prompt {prompt.name} exists but eval {eval_f.name} may target stale content",
                    ))
            else:
                report.findings.append(DriftFinding(
                    prompt_path=None,
                    eval_path=eval_f.path,
                    drift_type="orphan_eval",
                    severity="low",
                    detail=f"Eval {eval_f.name} has no corresponding prompt",
                ))

    # Avaliações que parecem ter sido atualizadas mais recentemente que prompts
    for prompt in prompts:
        for eval_f in evals:
            if _prompt_eval_match(prompt.path, eval_f.path):
                # Nome muito similar sugere que são "casal" prompt+eval
                if _similar_names(prompt.path, eval_f.path):
                    report.findings.append(DriftFinding(
                        prompt_path=prompt.path,
                        eval_path=eval_f.path,
                        drift_type=ADVISORY_FINDING_TYPE,
                        severity="medium",
                        detail=f"Prompt/Eval pair {prompt.name}/{eval_f.name} — verify they are in sync",
                    ))

    # `potential_drift` is advisory and excluded from the exit code.
    #
    # Every matched pair produced this finding, and it counted toward
    # `drift_count`, so a correctly paired project exited 1 forever. There is
    # no signal available today that separates a genuinely drifted pair from
    # a correctly paired one — semantic comparison is a roadmap item, not
    # implemented — so counting this finding means the gate is always red. An
    # always-red gate gets ignored or disabled, which destroys the one signal
    # that does work. The finding is still emitted: it is real information for
    # a human reviewer, it just no longer decides the exit code.
    #
    # Every other finding type counts, including the low-severity orphans.
    # Counting by severity threshold instead would be the same fail-open class
    # as the allowlist this replaces: `orphan_eval` is severity "low", and a
    # report holding findings must never print "No drift detected".
    report.drift_count = sum(
        1 for f in report.findings if f.drift_type != ADVISORY_FINDING_TYPE
    )
    return report


def _prompt_eval_match(prompt_path: Path, eval_path: Path) -> bool:
    """Verifica se um prompt e uma avaliação estão relacionados.

    Matching is by file stem only, which covers the convention this tool
    targets: ``prompts/summarizer.prompt`` pairs with
    ``evals/test_summarizer.py`` because ``'summarizer' in 'test_summarizer'``.

    Directory layout deliberately plays no part. An earlier version also
    matched on a shared parent directory, but ``Path.parents`` walks up to
    ``/``, whose ``.name`` is ``''`` — so the two name sets always intersected
    and every prompt matched every eval. That made the coverage-gap finding
    unreachable: a prompt with no eval at all was reported as evaluated.
    """
    p_stem = prompt_path.stem
    e_stem = eval_path.stem

    # Mesmo nome base
    if p_stem == e_stem:
        return True
    if p_stem in e_stem or e_stem in p_stem:
        return True

    return False


def _similar_names(a: Path, b: Path) -> bool:
    """Verifica se dois paths têm nomes semanticamente similares."""
    a_stem = a.stem.lower().replace("-", "").replace("_", "")
    b_stem = b.stem.lower().replace("-", "").replace("_", "")
    if a_stem == b_stem:
        return True
    if len(a_stem) > 3 and len(b_stem) > 3:
        if a_stem[:3] == b_stem[:3] or a_stem[-3:] == b_stem[-3:]:
            return True
    return False
