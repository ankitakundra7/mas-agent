"""MAS Agent CLI — Score a repository's agent-readiness.

Uses Claude Code CLI (same as Paper2Agent) — no separate API key needed.

Usage:
    mas-score https://github.com/owner/repo
    mas-score https://github.com/owner/repo --abstract "Paper abstract..."
    mas-score /path/to/local/repo --local
"""

import sys
import time
import tempfile
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from mas_agent.repo_fetcher import clone_repo, RepoInfo
from mas_agent.analyzers.structure import analyze_structure, format_evidence
from mas_agent.analyzers.dependencies import analyze_dependencies, format_dep_evidence
from mas_agent.agent import score_repository
from mas_agent.report import to_markdown, to_json, format_score_bar

console = Console()


def print_score_table(scores: dict, name: str):
    table = Table(title=f"MAS Scores: {name}", show_header=True)
    table.add_column("Dimension", style="bold")
    table.add_column("Score", justify="center")
    table.add_column("Bar")
    table.add_column("Key Finding", style="dim", max_width=60)

    for dim in ["completeness", "clarity", "modularity", "reproducibility", "executability"]:
        d = scores.get(dim, {})
        if not isinstance(d, dict): continue
        s = d.get("score", 0)
        color = "green" if s >= 2 else "yellow" if s == 1 else "red"
        r = d.get("reasoning", "")
        table.add_row(dim.capitalize(), f"[{color}]{s}/3[/{color}]",
                      format_score_bar(s), (r[:80] + "...") if len(r) > 80 else r)

    console.print(table)
    console.print()
    total = scores.get("total_score", 0)
    ready = scores.get("agent_ready", False)
    cl = scores.get("classification", "Unknown")
    color = "green" if ready else "red"
    console.print(f"[bold]Total Score:[/bold] [{color}]{total}/15[/{color}]")
    console.print(f"[bold]Classification:[/bold] [{color}]{cl}[/{color}]")


@click.command()
@click.argument("repo_url")
@click.option("--abstract", "-a", default="", help="Paper abstract for better identification")
@click.option("--local", "-l", is_flag=True, help="Treat repo_url as local path")
@click.option("--output", "-o", default="", help="Output file path (without extension)")
@click.option("--format", "-f", "fmt", type=click.Choice(["markdown", "json", "both"]), default="markdown")
@click.option("--clone-dir", default="", help="Clone directory (default: temp)")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--timeout", "-t", default=600, help="Max seconds for agent scoring (default: 600)")
def main(repo_url, abstract, local, output, fmt, clone_dir, verbose, timeout):
    """Score a GitHub repository's agent-readiness using MAS.
    
    Requires Claude Code CLI (claude) to be installed and configured.
    Uses the same infrastructure as Paper2Agent — no separate API key needed.
    """
    console.print(Panel.fit(
        "[bold blue]MAS Agent[/bold blue] — Model Agent Specification Scorer\n"
        "[dim]Powered by Claude Code CLI (same as Paper2Agent)[/dim]",
        border_style="blue"
    ))

    # Check claude CLI availability
    import shutil
    if not shutil.which("claude"):
        console.print("[red]Error: claude CLI not found. Install Claude Code first.[/red]")
        console.print("[dim]See: https://docs.anthropic.com/en/docs/claude-code[/dim]")
        sys.exit(1)

    start = time.time()

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:

        # Step 1: Get repo
        t1 = progress.add_task("Fetching repository...", total=None)
        if local:
            p = Path(repo_url).resolve()
            if not p.exists():
                console.print(f"[red]Path not found: {p}[/red]")
                sys.exit(1)
            repo_info = RepoInfo(url=repo_url, owner="local", name=p.name, local_path=p)
        else:
            target = Path(clone_dir) if clone_dir else Path(tempfile.mkdtemp(prefix="mas_"))
            repo_info = clone_repo(repo_url, target)
        if not repo_info.clone_success:
            console.print(f"[red]Clone failed: {repo_info.clone_error}[/red]")
            sys.exit(1)
        progress.update(t1, description=f"✓ Repository: {repo_info.name}")

        # Step 2: Evidence gathering (rule-based)
        t2 = progress.add_task("Analyzing structure...", total=None)
        structure = analyze_structure(repo_info.local_path)
        se = format_evidence(structure)
        progress.update(t2, description=f"✓ {len(structure.notebooks)} notebooks, {len(structure.python_scripts)} scripts")

        t3 = progress.add_task("Analyzing dependencies...", total=None)
        deps = analyze_dependencies(repo_info.local_path)
        de = format_dep_evidence(deps)
        progress.update(t3, description=f"✓ {deps.total_deps} deps, frameworks={deps.frameworks}")

        # Step 3: Agent scoring via Claude Code CLI
        t4 = progress.add_task("MAS Agent scoring (Claude Code reading files)...", total=None)
        scores = score_repository(repo_info.local_path, se, de, abstract, timeout)
        progress.update(t4, description="✓ MAS Agent scoring complete")

    duration = time.time() - start
    console.print()

    if "error" in scores:
        console.print(f"[red]Agent error: {scores['error']}[/red]")
        if "raw_response" in scores:
            console.print(f"[dim]{scores['raw_response'][:500]}[/dim]")
    else:
        print_score_table(scores, repo_info.name)
        
        # Show cost comparison
        mas_cost = scores.get("mas_cost_usd", 0.0)
        if mas_cost > 0:
            console.print(f"\n[bold]MAS Cost:[/bold] ${mas_cost:.4f}")
            console.print(f"[dim]Paper2Agent average cost: $5-20 per conversion attempt[/dim]")
            console.print(f"[dim]Savings if not agent-ready: ${5 - mas_cost:.2f} to ${20 - mas_cost:.2f} per paper[/dim]")
        
        recs = scores.get("recommendations", [])
        if recs:
            console.print("\n[bold]Recommendations:[/bold]")
            for r in recs: console.print(f"  • {r}")

    if output:
        p = Path(output)
        if fmt in ("json", "both"):
            p.with_suffix(".json").write_text(to_json(scores, repo_url, duration))
            console.print(f"\n[green]JSON: {p.with_suffix('.json')}[/green]")
        if fmt in ("markdown", "both"):
            p.with_suffix(".md").write_text(to_markdown(scores, repo_url, duration))
            console.print(f"[green]Markdown: {p.with_suffix('.md')}[/green]")
    elif verbose:
        console.print("\n" + to_markdown(scores, repo_url, duration))

    console.print(f"\n[dim]Completed in {duration:.1f}s[/dim]")
    sys.exit(0 if scores.get("agent_ready", False) else 1)


if __name__ == "__main__":
    main()
