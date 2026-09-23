"""CLI para prompt-drift."""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from prompt_drift.scanner import scan_directory, collect_prompts, collect_evals
from prompt_drift.detectors import detect_drift, DriftReport

console = Console()


@click.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
@click.option("--no-progress", is_flag=True, help="Suppress progress output")
def main(path: str, output_json: bool, no_progress: bool):
    """Detect drift between LLM prompts and their evaluation tests.

    Exemplus:
        prompt-drift ./my-project
        prompt-drift ./my-project --json
    """
    root = Path(path).resolve()
    console.print(f"[bold]Scanning[/bold] [cyan]{root}[/cyan]")

    prompts = collect_prompts(root)
    evals = collect_evals(root)

    if not no_progress:
        console.print(
            f"  Found [green]{len(prompts)}[/green] prompts, "
            f"[yellow]{len(evals)}[/yellow] evals"
        )

    report = detect_drift(prompts, evals, root)

    if output_json:
        findings_json = []
        for f in report.findings:
            findings_json.append({
                "type": f.drift_type,
                "severity": f.severity,
                "detail": f.detail,
                "prompt": str(f.prompt_path) if f.prompt_path else None,
                "eval": str(f.eval_path) if f.eval_path else None,
            })
        print(json.dumps({
            "root": str(root),
            "prompts": len(prompts),
            "evals": len(evals),
            "drift_count": report.drift_count,
            "exit_code": report.exit_code,
            "findings": findings_json,
        }, indent=2))
    else:
        _print_report(report, root)

    raise SystemExit(report.exit_code)


def _print_report(report: DriftReport, root: Path):
    if report.drift_count == 0:
        console.print(
            f"\n[bold green]No drift detected[/bold green] in [cyan]{root}[/cyan]"
        )
        console.print(
            f"  {report.total_prompts} prompts, "
            f"{report.total_evals} evals - all in sync"
        )
        return

    console.print(f"\n[bold red]Drift detected[/bold red] in [cyan]{root}[/cyan]")
    console.print(
        f"  {report.total_prompts} prompts, "
        f"{report.total_evals} evals, "
        f"[red]{report.drift_count} drift(s)[/red]"
    )

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Type", style="cyan", width=18)
    table.add_column("Severity", style="yellow", width=10)
    table.add_column("Detail", style="white")

    for finding in report.findings:
        sev_color = {
            "high": "red",
            "medium": "yellow",
            "low": "green",
        }.get(finding.severity, "white")

        detail = finding.detail
        if len(detail) > 80:
            detail = detail[:77] + "..."

        table.add_row(
            finding.drift_type,
            f"[{sev_color}]{finding.severity}[/{sev_color}]",
            detail,
        )

    console.print(table)
    console.print()


if __name__ == "__main__":
    main()
