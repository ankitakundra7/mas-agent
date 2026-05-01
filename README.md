# MAS Agent: Model Agent Specification Scorer

Automated agent-readiness scoring for research paper repositories. Uses Claude Code CLI, the same infrastructure as Paper2Agent. No separate API key needed.

## Prerequisites

- Python >= 3.10
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and configured
- `git` for cloning repositories

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Score a GitHub repository
mas-score https://github.com/owner/repo

Example: mas-score https://github.com/JCZ404/Semi-DETR

# With paper abstract for better method identification
mas-score https://github.com/owner/repo --abstract "We propose..."

Example: mas-score https://github.com/JCZ404/Semi-DETR --abstract "We propose Semi-DETR, a semi-supervised object detection method using detection transformers with a one-to-many assignment strategy for pseudo-label mining"

# Score a local repo (no cloning)
mas-score /path/to/repo --local

Example: mas-score C:/Users/xyz/semidetr_agent/repo/Semi-DETR --local


# Save reports
mas-score https://github.com/JCZ404/Semi-DETR --output semidetr_report --format both --verbose
```

## How It Works

**Phase 1: Evidence Gathering (rule-based, instant):**
Clone repo, analyze file structure, parse dependencies, detect frameworks.

**Phase 2: Agent Scoring (Claude Code, ~2-5 min):**
Claude Code agent receives evidence + repo access. It reads README, Python files, notebooks, and .gitmodules to score all 5 dimensions with nuanced judgment.

## Dimensions

| Dimension | What It Measures |
|-----------|-----------------|
| **Completeness** | Components exist AND are discoverable by scanners |
| **Clarity** | Method description precision and documentation quality |
| **Modularity** | Component independence and separation |
| **Reproducibility** | Environment creation feasibility |
| **Executability** | End-to-end runnability on standard hardware |

## Relationship to Paper2Agent

MAS is a **pre-screening layer**, not a replacement. Paper2Agent's scanner evaluates files ("is this tutorial good?"). MAS evaluates the system ("will the pipeline succeed?"). Running MAS first saves $10-$30+ per failed conversion.
