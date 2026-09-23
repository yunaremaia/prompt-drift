"""Detecção de drift entre prompts e avaliações."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from prompt_drift.scanner import PromptFile, EvalFile


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
    """
    if root is None:
        root = Path.cwd()

    report = DriftReport(
        total_prompts=len(prompts),
        total_evals=len(evals),
    )

    if not prompts and not evals:
        return report

    prompt_names = {p.name for p in prompts}
    eval_names = {e.name for e in evals}

    # Prompts sem avaliação correspondente
    for prompt in prompts:
        matching_evals = [e for e in evals
                         if _prompt_eval_match(prompt.path, e.path)]
        if not matching_evals:
            # Tentar encontrar por nome similar
            prompt_base = prompt.path.stem
            similar = [e for e in evals
                      if prompt_base in e.path.stem or e.path.stem in prompt_base]
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
                report.drift_count += 1

    # Avaliações sem prompt correspondente
    for eval_f in evals:
        matching_prompts = [p for p in prompts
                           if _prompt_eval_match(p.path, eval_f.path)]
        if not matching_prompts:
            eval_base = eval_f.path.stem
            similar = [p for p in prompts
                      if eval_base in p.path.stem or p.path.stem in eval_base]
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
                        drift_type="potential_drift",
                        severity="medium",
                        detail=f"Prompt/Eval pair {prompt.name}/{eval_f.name} — verify they are in sync",
                    ))

    report.drift_count = len([f for f in report.findings
                              if f.drift_type in ("unEval'd_prompt", "potential_drift")])
    return report


def _prompt_eval_match(prompt_path: Path, eval_path: Path) -> bool:
    """Verifica se um prompt e uma avaliação estão relacionados."""
    p_stem = prompt_path.stem
    e_stem = eval_path.stem

    # Mesmo nome base
    if p_stem == e_stem:
        return True
    if p_stem in e_stem or e_stem in p_stem:
        return True

    # Conteúdo de diretório similar (ambos em prompts/ e evals/)
    p_parents = {p.name for p in prompt_path.parents}
    e_parents = {e.name for e in eval_path.parents}
    if p_parents & e_parents:
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
