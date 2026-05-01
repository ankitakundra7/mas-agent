"""Dependency analysis — rule-based evidence for the agent."""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DependencyAnalysis:
    has_any_dep_spec: bool = False
    dep_spec_type: str = ""
    total_deps: int = 0
    pinned_deps: int = 0
    frameworks: list = field(default_factory=list)
    framework_conflicts: list = field(default_factory=list)
    ssh_deps: list = field(default_factory=list)
    ssh_submodules: list = field(default_factory=list)
    git_deps: list = field(default_factory=list)
    custom_packages: list = field(default_factory=list)
    requires_gpu: bool = False
    requires_multi_gpu: bool = False
    cuda_version: str = ""
    feasibility_issues: list = field(default_factory=list)


def analyze_dependencies(repo_path: Path) -> DependencyAnalysis:
    a = DependencyAnalysis()
    req = repo_path / "requirements.txt"
    if req.exists():
        a.has_any_dep_spec, a.dep_spec_type = True, "requirements.txt"
        for line in req.read_text(errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"): continue
            a.total_deps += 1
            if "==" in line: a.pinned_deps += 1
            if "git+" in line or "github.com" in line:
                a.git_deps.append(line)
                if "git@" in line: a.ssh_deps.append(line)
    elif (repo_path / "pyproject.toml").exists():
        a.has_any_dep_spec, a.dep_spec_type = True, "pyproject.toml"
    elif (repo_path / "setup.py").exists():
        a.has_any_dep_spec, a.dep_spec_type = True, "setup.py"

    # Frameworks
    fw = set()
    fm = {"torch": "pytorch", "tensorflow": "tensorflow", "jax": "jax",
          "flax": "jax", "keras": "tensorflow"}
    for f in sorted(repo_path.rglob("*.py"), key=lambda p: p.stat().st_size, reverse=True)[:20]:
        try:
            c = f.read_text(errors="ignore")[:5000]
            for k, v in fm.items():
                if f"import {k}" in c or f"from {k}" in c: fw.add(v)
        except: pass
    a.frameworks = sorted(fw)
    if len(fw) > 1: a.framework_conflicts = [f"Multiple: {', '.join(fw)}"]

    # Compute
    for name in ["README.md", "readme.md", "TRAINING.md", "INSTALL.md"]:
        p = repo_path / name
        if not p.exists(): continue
        try:
            c = p.read_text(errors="ignore").lower()
            if any(t in c for t in ["gpu", "cuda", "nvidia"]): a.requires_gpu = True
            if any(t in c for t in ["multi-gpu", "8 gpus", "64 gpu", "multi-node"]): a.requires_multi_gpu = True
            m = re.search(r"cuda\s*[>=<]*\s*(\d+\.\d+)", c)
            if m: a.cuda_version = m.group(1)
        except: pass

    # Custom packages
    for sp in repo_path.rglob("setup.py"):
        if sp.parent != repo_path:
            parts = set(sp.relative_to(repo_path).parts)
            if not (parts & {"test", "tests", "examples", "docs", ".git"}):
                a.custom_packages.append(str(sp.relative_to(repo_path).parent))

    # SSH submodules
    gm = repo_path / ".gitmodules"
    if gm.exists():
        for line in gm.read_text(errors="ignore").splitlines():
            if line.strip().startswith("url") and "=" in line:
                u = line.split("=", 1)[1].strip()
                if u.startswith("git@") or u.startswith("ssh://"): a.ssh_submodules.append(u)

    # Issues
    if a.ssh_deps or a.ssh_submodules: a.feasibility_issues.append(f"SSH-only: {a.ssh_deps + a.ssh_submodules}")
    if not a.has_any_dep_spec: a.feasibility_issues.append("No dependency spec found")
    if a.requires_multi_gpu: a.feasibility_issues.append("Requires multi-GPU")
    if a.custom_packages: a.feasibility_issues.append(f"Custom packages: {a.custom_packages}")
    if a.framework_conflicts: a.feasibility_issues.append(a.framework_conflicts[0])
    return a


def format_dep_evidence(a: DependencyAnalysis) -> str:
    lines = ["# Dependency Evidence",
             f"Spec: {'Y ' + a.dep_spec_type if a.has_any_dep_spec else 'N'}",
             f"Deps: {a.total_deps}, Pinned: {a.pinned_deps}",
             f"Frameworks: {', '.join(a.frameworks) if a.frameworks else 'none'}",
             f"SSH deps: {a.ssh_deps or 'none'}",
             f"SSH submodules: {a.ssh_submodules or 'none'}",
             f"Custom packages: {a.custom_packages or 'none'}",
             f"GPU: {a.requires_gpu}, Multi-GPU: {a.requires_multi_gpu}"]
    if a.cuda_version: lines.append(f"CUDA: {a.cuda_version}")
    if a.feasibility_issues:
        lines.append("\n## Issues")
        for i in a.feasibility_issues: lines.append(f"  ! {i}")
    return "\n".join(lines)
