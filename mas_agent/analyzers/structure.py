"""Analyze repository structure — rule-based evidence for the agent."""

import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileInfo:
    path: str
    extension: str
    size_bytes: int
    directory: str

@dataclass
class StructureAnalysis:
    repo_path: Path
    repo_name: str
    total_files: int = 0
    notebooks: list = field(default_factory=list)
    python_scripts: list = field(default_factory=list)
    markdown_files: list = field(default_factory=list)
    data_files: list = field(default_factory=list)
    test_files: list = field(default_factory=list)
    has_requirements_txt: bool = False
    has_pyproject_toml: bool = False
    has_setup_py: bool = False
    has_environment_yml: bool = False
    has_dockerfile: bool = False
    has_readme: bool = False
    has_install_md: bool = False
    has_manifest: bool = False
    has_gitmodules: bool = False
    has_docs_dir: bool = False
    has_examples_dir: bool = False
    has_tests_dir: bool = False
    has_src_dir: bool = False
    has_models_dir: bool = False
    has_data_dir: bool = False
    has_demo_dir: bool = False
    top_level_dirs: list = field(default_factory=list)
    extension_counts: dict = field(default_factory=dict)
    dep_count: int = 0
    pinned_deps: bool = False


SKIP = {".git", "__pycache__", "node_modules", ".tox", ".eggs", ".mypy_cache",
        ".pytest_cache", "venv", "env", ".venv", ".env"}
DATA_EXT = {".csv", ".tsv", ".npy", ".npz", ".h5", ".hdf5", ".pkl", ".pt", ".pth",
            ".ckpt", ".safetensors", ".parquet"}
TEST_DIRS = {"test", "tests", "testing"}


def analyze_structure(repo_path: Path) -> StructureAnalysis:
    a = StructureAnalysis(repo_path=repo_path, repo_name=repo_path.name)
    ext_counter = Counter()
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.endswith(".egg-info")]
        rel_root = os.path.relpath(root, repo_path)
        if rel_root == ".":
            a.top_level_dirs = sorted(dirs)
        for fname in files:
            fp = Path(root) / fname
            try: size = fp.stat().st_size
            except OSError: continue
            rel = os.path.relpath(fp, repo_path)
            ext = Path(fname).suffix.lower()
            ext_counter[ext] += 1
            a.total_files += 1
            d = str(Path(rel).parent) if str(Path(rel).parent) != "." else ""
            parts = set(Path(rel).parts)
            is_test = bool(parts & TEST_DIRS) or fname.startswith("test_") or fname.endswith("_test.py")
            info = FileInfo(path=rel, extension=ext, size_bytes=size, directory=d)
            if ext == ".ipynb": a.notebooks.append(info)
            if ext == ".py" and not is_test: a.python_scripts.append(info)
            if ext in {".md", ".rst", ".txt"}: a.markdown_files.append(info)
            if is_test: a.test_files.append(info)
            if ext in DATA_EXT: a.data_files.append(info)

    a.has_requirements_txt = (repo_path / "requirements.txt").exists()
    a.has_pyproject_toml = (repo_path / "pyproject.toml").exists()
    a.has_setup_py = (repo_path / "setup.py").exists()
    a.has_environment_yml = any((repo_path / n).exists() for n in ["environment.yml", "environment.yaml"])
    a.has_dockerfile = any((repo_path / n).exists() for n in ["Dockerfile", "docker-compose.yml"])
    a.has_gitmodules = (repo_path / ".gitmodules").exists()
    for f in os.listdir(repo_path):
        fl = f.lower()
        if fl.startswith("readme"): a.has_readme = True
        if fl in ("install.md", "installation.md"): a.has_install_md = True
        if fl in ("contribution.md", "manifest.md", "contributions.md"): a.has_manifest = True

    if a.has_requirements_txt:
        lines = (repo_path / "requirements.txt").read_text(errors="ignore").splitlines()
        deps = [l.strip() for l in lines if l.strip() and not l.startswith("#") and not l.startswith("-")]
        a.dep_count = len(deps)
        a.pinned_deps = sum(1 for d in deps if "==" in d) > len(deps) * 0.5 if deps else False

    top = {d.lower() for d in a.top_level_dirs}
    a.has_docs_dir = bool({"docs", "doc"} & top)
    a.has_examples_dir = bool({"examples", "example"} & top)
    a.has_tests_dir = bool({"tests", "test"} & top)
    a.has_src_dir = bool({"src"} & top)
    a.has_models_dir = bool({"models", "model"} & top)
    a.has_data_dir = bool({"data", "datasets"} & top)
    a.has_demo_dir = bool({"demo", "demos"} & top)
    a.extension_counts = dict(ext_counter)
    return a


def format_evidence(a: StructureAnalysis) -> str:
    lines = [f"# Repository Structure: {a.repo_name}", f"Total files: {a.total_files}",
             f"Top-level dirs: {', '.join(a.top_level_dirs)}", "", "## Key Files"]
    for check, label in [(a.has_readme, "README"), (a.has_requirements_txt, "requirements.txt"),
        (a.has_pyproject_toml, "pyproject.toml"), (a.has_setup_py, "setup.py"),
        (a.has_dockerfile, "Dockerfile"), (a.has_environment_yml, "environment.yml"),
        (a.has_gitmodules, ".gitmodules"), (a.has_manifest, "CONTRIBUTION.md/manifest"),
        (a.has_install_md, "INSTALL.md")]:
        lines.append(f"  {'Y' if check else 'N'} {label}")
    if a.has_requirements_txt:
        lines.append(f"  Deps: {a.dep_count}, pinned={a.pinned_deps}")

    lines.append(f"\n## Notebooks ({len(a.notebooks)})")
    for nb in a.notebooks[:20]:
        lines.append(f"  {nb.path} ({nb.size_bytes // 1024}KB)")
    lines.append(f"\n## Python Scripts ({len(a.python_scripts)})")
    by_dir = defaultdict(list)
    for s in a.python_scripts: by_dir[s.directory or "(root)"].append(s)
    for d in sorted(by_dir)[:15]:
        lines.append(f"  [{d}/] ({len(by_dir[d])} files)")
        for s in by_dir[d][:5]: lines.append(f"    {s.path}")
    lines.append(f"\n## Data Files ({len(a.data_files)})")
    for df in a.data_files[:10]: lines.append(f"  {df.path}")
    lines.append(f"\n## Dirs: docs={a.has_docs_dir} examples={a.has_examples_dir} src={a.has_src_dir} "
                 f"models={a.has_models_dir} data={a.has_data_dir} demo={a.has_demo_dir} tests={a.has_tests_dir}")
    return "\n".join(lines)
