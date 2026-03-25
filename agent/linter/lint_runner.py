"""Runs ESLint (JS/TS) or flake8/ruff (Python) on the files being committed."""

import subprocess
import shutil
import os
from pathlib import Path
from typing import List, Optional

from agent.utils.logger import get_logger

logger = get_logger(__name__)

# ANSI colours
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"


def run_linting(
    files: List[str],
    language: str,
    project_root: str,
    python_linter: str = "auto",   # "flake8" | "ruff" | "auto"
    js_linter: str = "eslint",
) -> int:
    """Run the appropriate linter for the given language.

    Args:
        files:         List of file paths to lint.
        language:      Detected project language.
        project_root:  Root directory of the project.
        python_linter: Which Python linter to use ("auto" tries ruff then flake8).
        js_linter:     Which JS linter to use (currently only "eslint").

    Returns:
        0 if linting passed, 1 if there are errors.
    """
    py_files = [f for f in files if f.endswith(".py")]
    js_files = [f for f in files if Path(f).suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs"}]

    exit_code = 0

    if py_files:
        exit_code |= _run_python_linter(py_files, python_linter)

    if js_files:
        exit_code |= _run_eslint(js_files, project_root, js_linter)

    return exit_code


# ── Python ────────────────────────────────────────────────────────────────────

def _run_python_linter(files: List[str], linter: str) -> int:
    """Run ruff or flake8 on Python files."""
    tool = _pick_python_linter(linter)

    if tool is None:
        print(
            f"{_YELLOW}[LINT] No Python linter found. "
            f"Install ruff (`pip install ruff`) or flake8 (`pip install flake8`).{_RESET}"
        )
        return 0  # Skip, don't block

    print(f"\n{_CYAN}{_BOLD}── Python Linting ({tool}) {'─' * 40}{_RESET}")

    if tool == "ruff":
        return _run_subprocess([tool, "check", "--output-format=concise"] + files)
    else:  # flake8
        return _run_subprocess([tool, "--max-line-length=120"] + files)


def _pick_python_linter(preference: str) -> Optional[str]:
    """Return the linter binary to use, or None if nothing is installed."""
    if preference == "ruff":
        return "ruff" if shutil.which("ruff") else None
    if preference == "flake8":
        return "flake8" if shutil.which("flake8") else None
    # auto — prefer ruff (faster), fallback to flake8
    if shutil.which("ruff"):
        return "ruff"
    if shutil.which("flake8"):
        return "flake8"
    return None


# ── JavaScript / TypeScript ───────────────────────────────────────────────────

def _run_eslint(files: List[str], project_root: str, linter: str) -> int:
    """Run ESLint on JS/TS files.

    Groups files by their nearest ESLint config root and runs ESLint
    once per config root so monorepos (client/ + server/) both get linted.
    """
    # Resolve all paths to absolute so ESLint receives unambiguous paths
    # regardless of what cwd it runs from (important for monorepos / staged files)
    abs_files = [
        str(Path(f) if Path(f).is_absolute() else Path(project_root) / f)
        for f in files
    ]

    # Group files by the config root nearest to them
    groups: dict = {}
    for f in abs_files:
        config_root = _find_eslint_config_root(f, project_root)
        if config_root:
            groups.setdefault(config_root, []).append(f)
        # Files with no config are silently skipped

    if not groups:
        print(
            f"{_YELLOW}[LINT] No ESLint config found in {project_root} "
            f"or any subdirectory. Skipping JS linting.{_RESET}"
        )
        return 0

    exit_code = 0
    print(f"\n{_CYAN}{_BOLD}── JavaScript Linting (ESLint) {'─' * 37}{_RESET}")

    for config_root, group_files in groups.items():
        eslint_bin = _find_eslint(config_root)
        if eslint_bin is None:
            print(
                f"{_YELLOW}[LINT] ESLint not found in {config_root}. "
                f"Install it: npm install --save-dev eslint{_RESET}"
            )
            continue
        exit_code |= _run_subprocess(
            [eslint_bin, "--format=stylish"] + group_files,
            cwd=config_root,
        )

    return exit_code


def _find_eslint_config_root(file_path: str, stop_at: str) -> Optional[str]:
    """Walk upward from file_path until an ESLint config is found or stop_at is reached."""
    current = Path(file_path).resolve().parent
    stop = Path(stop_at).resolve()

    while True:
        if _has_eslint_config(str(current)):
            return str(current)
        if current == stop or current.parent == current:
            break
        current = current.parent

    # Also check stop_at itself
    if _has_eslint_config(str(stop)):
        return str(stop)
    return None


def _find_eslint(project_root: str) -> Optional[str]:
    """Find ESLint binary: local node_modules first, then global."""
    local_win  = Path(project_root) / "node_modules" / ".bin" / "eslint.cmd"
    local_unix = Path(project_root) / "node_modules" / ".bin" / "eslint"
    if local_win.exists():
        return str(local_win)
    if local_unix.exists():
        return str(local_unix)
    if shutil.which("eslint"):
        return "eslint"
    if shutil.which("npx"):
        return "npx eslint"
    return None


def _has_eslint_config(project_root: str) -> bool:
    """Return True if any ESLint config file exists in project_root."""
    config_files = [
        ".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json",
        ".eslintrc.yaml", ".eslintrc.yml", "eslint.config.js", "eslint.config.mjs",
    ]
    root = Path(project_root)
    # Also check if eslintConfig is in package.json
    pkg = root / "package.json"
    if pkg.exists():
        try:
            import json
            data = json.loads(pkg.read_text(encoding="utf-8"))
            if "eslintConfig" in data:
                return True
        except Exception:
            pass
    return any((root / f).exists() for f in config_files)


# ── Shared ────────────────────────────────────────────────────────────────────

def _run_subprocess(cmd: List[str], cwd: Optional[str] = None) -> int:
    """Run a command, stream its output, and return the exit code."""
    # Handle "npx eslint" which comes as a single string
    if len(cmd) == 1 and " " in cmd[0]:
        cmd = cmd[0].split() + cmd[1:]

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=False,   # stream output directly to terminal
            text=True,
        )
        if result.returncode != 0:
            print(f"\n{_RED}[LINT] Linting failed — fix the above errors before committing.{_RESET}\n")
        else:
            print(f"{_CYAN}[LINT] No linting errors found.{_RESET}")
        return result.returncode
    except FileNotFoundError:
        logger.warning("Linter binary not found: %s", cmd[0])
        return 0  # Don't block if binary missing
