"""MAS Scoring Agent — runs through Claude Code CLI.

Uses the same infrastructure as Paper2Agent:
- `claude` CLI with --dangerously-skip-permissions
- Claude Code can read files, list directories, run bash
- Agentic loop: Claude reasons, uses tools, produces scores

This means MAS works if Paper2Agent works — no separate API key needed.
"""

import json
import subprocess
import os
from pathlib import Path


MAS_PROMPT_TEMPLATE = """You are the MAS (Model Agent Specification) scoring agent. You are evaluating 
the repository at: {repo_path}

Your job is to determine whether this repository can be RELIABLY converted into an executable 
AI agent by Paper2Agent. You must be SKEPTICAL — good documentation does NOT mean the pipeline 
will succeed. Score based on OPERATIONAL REALITY, not documentation quality.

{abstract_section}

## Pre-gathered Evidence

{structure_evidence}

{dep_evidence}

## MANDATORY VERIFICATION STEPS (do these BEFORE scoring)

You MUST answer these questions by reading actual files. Do NOT assume — verify.

### V1: Scanner Behavior Prediction
Paper2Agent's scanner has this STRICT rule: "Python scripts (.py) included only when no .ipynb or .md tutorials exist."
- Are there ANY .ipynb files in this repo? If YES, ALL .py files will be EXCLUDED from scanning.
- If .py files are excluded, what will the scanner select instead?
- CRITICAL CHECK: Read at least one notebook. Does it import and use THIS REPO's own package/methods?
  - If YES (e.g., "import scanpy as sc; sc.pp.normalize(adata)") → "Relevant notebook" pattern. Notebooks ARE valid 
    tutorials of the core method. Scanner selecting them is CORRECT.
  - If NO (e.g., notebook imports unrelated libraries, is a generic tutorial) → "Misaligned notebook" pattern. Notebooks 
    are peripheral content. Scanner selecting them MISSES the core method.
- This distinction determines whether Completeness scores 1 (misaligned) or 2-3 (relevant).

### V2: Sample Data Availability
- Is there actual runnable sample data IN the repository (not just referenced, not requiring download)?
- Check: Are there .csv, .npy, .h5, .pt files in a data/ directory, or are there only config/YAML files?
- Config files and YAML files are NOT sample data. Test fixture configs are NOT sample data.
- If the README says "download dataset from [URL]", that means sample data is NOT included.

### V3: Demo Runnability
- Is there a demo script/notebook that can run WITHOUT downloading external datasets?
- Can it run on CPU within 30 minutes?
- Does it produce meaningful scientific output (not just "setup complete" or data preprocessing)?
- A data preprocessing notebook is NOT a demo of the core method.

### V4: Environment Feasibility
- Does pip install actually work with the listed dependencies?
- Are there custom CUDA operators or C++ extensions that need compilation?
- Are there dependencies that require specific hardware?

## SCORING RULES (be strict)

### COMPLETENESS (Content + Structural Discoverability)
- Score 3 ONLY IF: Core method is demonstrated in .ipynb notebooks AND sample data included AND manifest or clear README
- Score 2 IF: Core method identifiable and notebooks demonstrate it, but sample data requires download
- Score 1 IF: Core method is in .py files AND .ipynb files exist that are UNRELATED peripheral content 
  (scanner will select wrong content). OR critical content gaps.
- Score 0 IF: No code, no docs

CRITICAL DISTINCTION — two different patterns:
- RELEVANT NOTEBOOKS: (score 2-3): The .ipynb notebooks ARE tutorials of the core method. They show how to 
  use the library's scientific functions (preprocessing, clustering, visualization). The .py files are 
  the library implementation. Scanner selecting notebooks IS correct behavior here because the notebooks 
  demonstrate the paper's contribution.
- MISALIGNED NOTEBOOKS (score 1): The .ipynb notebooks are UNRELATED peripheral content (e.g., bundled dependency 
  tutorials). The core method is ONLY in .py files. Scanner selecting notebooks means the core method 
  is completely missed.

To distinguish: Read at least one notebook. Does it import and use the repo's own package/methods? 
If YES → relevant notebooks (scores 2-3). If NO → misaligned notebooks (score 1).

### CLARITY
- Score 3 ONLY IF: Every function has docstrings with types, no hardcoded paths, config system (argparse/hydra/yaml)
- Score 2 IF: Most documented, some gaps
- Score 1 IF: Minimal docs, hardcoded paths, implicit preprocessing
- Score 0 IF: No documentation

### MODULARITY
- Score 3 ONLY IF: Model importable independently (verified by checking for __main__ guards and no top-level side effects)
- Score 2 IF: Model separable but training coupled
- Score 1 IF: Tightly coupled, multiple interdependent custom packages
- Score 0 IF: Monolithic

### REPRODUCIBILITY
- Score 3 ONLY IF: Single-command install works, all deps on PyPI, no SSH URLs, Docker provided
- Score 2 IF: Install works with effort, most deps on PyPI
- Score 1 IF: Install fails (SSH deps, CUDA compilation, custom packages not on PyPI)
- Score 0 IF: Cannot clone or no dependency spec

### EXECUTABILITY
- Score 3 ONLY IF: A demo exists that runs the CORE METHOD on readily available data (included in repo OR 
  downloadable via the library's own API like sc.datasets.pbmc3k()), on CPU, in <30 min
- Score 2 IF: Demo exists but needs minor setup (download one checkpoint, set one path, or uses library's 
  built-in dataset download)
- Score 1 IF: No demo of core method, OR demo requires large manual data download, OR requires multi-GPU
- Score 0 IF: Nothing runs without major infrastructure

CRITICAL: A data preprocessing notebook is NOT a demo of the core method. Score Executability based on 
whether the paper's NOVEL CONTRIBUTION can be demonstrated, not whether any notebook runs.
NOTE: If the library provides built-in dataset functions (e.g., scanpy.datasets.pbmc3k()), this counts 
as "readily available" — the user doesn't need to manually find and download data.

### Output Format
After verification and scoring, output ONLY a JSON object:

{{
  "verification": {{
    "v1_scanner": {{
      "ipynb_exist": true/false,
      "py_excluded": true/false,
      "scanner_would_select": ["list of files scanner picks"],
      "selection_is_core_method": true/false
    }},
    "v2_sample_data": {{
      "actual_data_files_in_repo": ["list or empty"],
      "requires_external_download": true/false,
      "data_included": true/false
    }},
    "v3_demo": {{
      "demo_exists": true/false,
      "demo_runs_core_method": true/false,
      "demo_needs_external_data": true/false,
      "demo_path": "path or null"
    }},
    "v4_environment": {{
      "pip_install_likely_works": true/false,
      "has_cuda_deps": true/false,
      "blocking_issues": []
    }}
  }},
  "completeness": {{
    "score": 0-3,
    "content_score": 0-3,
    "structural_score": 0-3,
    "reasoning": "explanation citing verification results",
    "core_files": ["paths"],
    "scanner_would_find": true/false,
    "scanner_would_select": ["what scanner picks"]
  }},
  "clarity": {{
    "score": 0-3,
    "reasoning": "explanation",
    "has_docstrings": true/false,
    "has_hardcoded_paths": true/false,
    "config_system": "argparse/hydra/yaml/none"
  }},
  "modularity": {{
    "score": 0-3,
    "reasoning": "explanation",
    "model_importable_independently": true/false,
    "custom_packages": []
  }},
  "reproducibility": {{
    "score": 0-3,
    "reasoning": "explanation",
    "env_install_likely_succeeds": true/false,
    "blocking_issues": []
  }},
  "executability": {{
    "score": 0-3,
    "reasoning": "explanation",
    "demo_exists": true/false,
    "demo_runs_core_method": true/false,
    "demo_path": "path or null",
    "cpu_capable": true/false
  }},
  "total_score": 0-15,
  "classification": "Agent-Ready|Conditionally Ready|Minimum Viable|Not Agent-Ready",
  "agent_ready": true/false,
  "recommendations": [
    "Specific actionable recommendation"
  ]
}}
"""


def score_repository(repo_path: Path, structure_evidence: str,
                     dep_evidence: str, paper_abstract: str = "",
                     timeout: int = 600) -> dict:
    """Run the MAS agent via Claude Code CLI.
    
    This mirrors how Paper2Agent runs its subagents:
    - Constructs a prompt with evidence
    - Pipes it to `claude` CLI
    - Claude Code reads files, reasons, produces scores
    
    Args:
        repo_path: Path to the cloned repository
        structure_evidence: Formatted structure analysis
        dep_evidence: Formatted dependency analysis  
        paper_abstract: Optional paper abstract
        timeout: Max seconds for claude CLI (default 10 min)
    
    Returns:
        Dictionary with scores for all 5 dimensions
    """
    abstract_section = ""
    if paper_abstract:
        abstract_section = f"## Paper Abstract\n{paper_abstract}"
    
    prompt = MAS_PROMPT_TEMPLATE.format(
        repo_path=str(repo_path.resolve()),
        abstract_section=abstract_section,
        structure_evidence=structure_evidence,
        dep_evidence=dep_evidence,
    )
    
    # Run through claude CLI — same as Paper2Agent
    # Use stream-json to capture cost data (same as Paper2Agent's step scripts)
    cmd = [
        "claude",
        "--model", "claude-sonnet-4-20250514",
        "--verbose",
        "--output-format", "stream-json",
        "--dangerously-skip-permissions",
        "-p", prompt,
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(repo_path.resolve()),
            encoding="utf-8",
            errors="replace",
        )
        
        if result.returncode != 0:
            return {
                "error": f"Claude CLI failed (exit code {result.returncode})",
                "stderr": (result.stderr or "")[:1000],
                "total_score": 0,
                "classification": "Error",
                "agent_ready": False,
                "mas_cost_usd": 0.0,
            }
        
        # Parse stream-json output — each line is a JSON object
        # The last "result" line contains both the response and cost data
        raw = (result.stdout or "").strip()
        response_text = ""
        mas_cost = 0.0
        
        if not raw:
            return {
                "error": "Empty response from Claude CLI",
                "total_score": 0,
                "classification": "Error",
                "agent_ready": False,
                "mas_cost_usd": 0.0,
            }
        
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                # Look for the result line (contains total_cost_usd)
                if obj.get("type") == "result":
                    response_text = obj.get("result", "")
                    mas_cost = obj.get("total_cost_usd", 0.0)
                    break
            except json.JSONDecodeError:
                continue
        
        if not response_text:
            # Fallback: try parsing entire output as single JSON
            try:
                outer = json.loads(raw)
                if isinstance(outer, dict):
                    response_text = outer.get("result", raw)
                    mas_cost = outer.get("total_cost_usd", 0.0)
            except json.JSONDecodeError:
                response_text = raw
        
        # Extract the scoring JSON from the response text
        try:
            if isinstance(response_text, str):
                start = response_text.find("{")
                end = response_text.rfind("}")
                if start != -1 and end != -1:
                    json_str = response_text[start:end + 1]
                    scores = json.loads(json_str)
                    scores["mas_cost_usd"] = round(mas_cost, 4)
                    return scores
                else:
                    return {
                        "error": "No JSON found in agent response",
                        "raw_response": response_text[:2000],
                        "total_score": 0,
                        "classification": "Error",
                        "agent_ready": False,
                        "mas_cost_usd": round(mas_cost, 4),
                    }
            elif isinstance(response_text, dict):
                response_text["mas_cost_usd"] = round(mas_cost, 4)
                return response_text
            else:
                scores = json.loads(str(response_text))
                scores["mas_cost_usd"] = round(mas_cost, 4)
                return scores
                
        except json.JSONDecodeError as e:
            return {
                "error": f"JSON parse error: {e}",
                "raw_response": str(response_text)[:2000],
                "total_score": 0,
                "classification": "Error",
                "agent_ready": False,
                "mas_cost_usd": round(mas_cost, 4),
            }
    
    except subprocess.TimeoutExpired:
        return {
            "error": f"Claude CLI timed out after {timeout}s",
            "total_score": 0,
            "classification": "Error",
            "agent_ready": False,
        }
    except FileNotFoundError:
        return {
            "error": "claude CLI not found. Install Claude Code: https://docs.anthropic.com/en/docs/claude-code",
            "total_score": 0,
            "classification": "Error",
            "agent_ready": False,
        }
    except Exception as e:
        return {
            "error": f"Unexpected error: {e}",
            "total_score": 0,
            "classification": "Error",
            "agent_ready": False,
        }
