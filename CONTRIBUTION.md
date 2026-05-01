# Core Contribution Files

## Core Method
- `mas_agent/agent.py`: MAS scoring agent — sends structured prompt to Claude Code CLI with repo evidence
- `mas_agent/cli.py`: CLI entry point (`mas-score` command)

## Evidence Gathering (rule-based)
- `mas_agent/analyzers/structure.py`: File structure analysis
- `mas_agent/analyzers/dependencies.py`: Dependency and environment feasibility analysis
- `mas_agent/repo_fetcher.py`: Repository cloning

## Report Generation
- `mas_agent/report.py`: Score report (JSON + Markdown) with recommendations

## Examples
- `examples/`: MAS scoring outputs for real repositories

