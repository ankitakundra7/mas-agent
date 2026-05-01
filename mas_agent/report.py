"""Generate MAS scoring reports."""

import json
from datetime import datetime


def format_score_bar(score: int) -> str:
    return f"[{'█' * score}{'░' * (3 - score)}] {score}/3"


def to_markdown(scores: dict, repo_url: str, duration: float) -> str:
    name = repo_url.rstrip("/").split("/")[-1]
    lines = [f"# MAS Report: {name}", f"**Repository:** {repo_url}",
             f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]

    total = scores.get("total_score", 0)
    classification = scores.get("classification", "Unknown")
    ready = scores.get("agent_ready", False)

    lines += ["## Summary", f"**Total Score: {total}/15**",
              f"**Classification: {classification}**",
              f"**Agent-Ready: {'Yes' if ready else 'No'}**"]
    
    mas_cost = scores.get("mas_cost_usd", 0.0)
    if mas_cost > 0:
        lines.append(f"**MAS Scoring Cost: ${mas_cost:.4f}**")
        lines.append(f"**Paper2Agent Cost (if run): $5–20**")
        if not ready:
            lines.append(f"**Estimated Savings: ${5 - mas_cost:.2f} to ${20 - mas_cost:.2f}**")
    
    lines += ["", "## Dimension Scores", ""]

    for dim in ["completeness", "clarity", "modularity", "reproducibility", "executability"]:
        d = scores.get(dim, {})
        if isinstance(d, dict):
            lines.append(f"**{dim.capitalize()}:** {format_score_bar(d.get('score', 0))}")

    lines.append("\n## Detailed Analysis")
    for dim in ["completeness", "clarity", "modularity", "reproducibility", "executability"]:
        d = scores.get(dim, {})
        if isinstance(d, dict):
            lines += [f"\n### {dim.capitalize()} ({d.get('score', 0)}/3)",
                      f"*{d.get('reasoning', 'N/A')}*"]
            if dim == "completeness":
                if "core_files" in d: lines.append(f"\nCore files: {d['core_files']}")
                if "scanner_would_find" in d: lines.append(f"Scanner finds core: {d['scanner_would_find']}")
            if dim == "executability":
                if d.get("demo_path"): lines.append(f"Demo: {d['demo_path']}")

    recs = scores.get("recommendations", [])
    if recs:
        lines.append("\n## Recommendations")
        for r in recs: lines.append(f"\n- {r}")

    lines.append(f"\n---\n*Completed in {duration:.1f}s*")
    return "\n".join(lines)


def to_json(scores: dict, repo_url: str, duration: float) -> str:
    return json.dumps({"repo_url": repo_url,
                       "scan_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                       "duration_seconds": round(duration, 1), **scores}, indent=2)
