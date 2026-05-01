"""Clone a GitHub repository following Paper2Agent's strategy."""

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RepoInfo:
    """Metadata about a cloned repository."""
    url: str
    owner: str
    name: str
    local_path: Path
    clone_success: bool = True
    clone_error: str = ""
    uses_ssh_submodules: bool = False
    ssh_submodule_urls: list = field(default_factory=list)


def parse_github_url(url: str) -> tuple[str, str]:
    """Extract owner and repo name from a GitHub URL."""
    url = url.rstrip("/").rstrip(".git")
    match = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", url)
    if not match:
        raise ValueError(f"Cannot parse GitHub URL: {url}")
    return match.group(1), match.group(2)


def clone_repo(url: str, target_dir: Path | None = None) -> RepoInfo:
    """Clone a repository using HTTPS with fallbacks (mirrors Paper2Agent's 02_clone_repo.sh)."""
    owner, name = parse_github_url(url)
    https_url = f"https://github.com/{owner}/{name}.git"
    if target_dir is None:
        target_dir = Path(tempfile.mkdtemp(prefix="mas_"))
    repo_path = target_dir / name
    info = RepoInfo(url=url, owner=owner, name=name, local_path=repo_path)

    if repo_path.exists():
        info.clone_success = True
    else:
        for cmd in [
            ["git", "clone", "--recurse-submodules", https_url, str(repo_path)],
            ["git", "clone", "--depth=1", https_url, str(repo_path)],
            ["git", "clone", https_url, str(repo_path)],
        ]:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if r.returncode == 0:
                    info.clone_success = True
                    break
            except (subprocess.TimeoutExpired, Exception) as e:
                info.clone_error = str(e)
        else:
            info.clone_success = False

    if info.clone_success and repo_path.exists():
        gitmodules = repo_path / ".gitmodules"
        if gitmodules.exists():
            for line in gitmodules.read_text(errors="ignore").splitlines():
                if line.strip().startswith("url") and "=" in line:
                    u = line.split("=", 1)[1].strip()
                    if u.startswith("git@") or u.startswith("ssh://"):
                        info.ssh_submodule_urls.append(u)
            info.uses_ssh_submodules = len(info.ssh_submodule_urls) > 0

    return info
