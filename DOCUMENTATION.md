# Code Review Agent — Technical Documentation

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Folder Structure](#2-folder-structure)
3. [Packages & Dependencies](#3-packages--dependencies)
4. [Architecture Overview](#4-architecture-overview)
5. [End-to-End Flow](#5-end-to-end-flow)
6. [Module Reference](#6-module-reference)
   - [main.py](#mainpy)
   - [agent/cli.py](#agentclipy)
   - [agent/hook_runner.py](#agenthook_runnerpy)
   - [agent/detector/](#agentdetector)
   - [agent/analyzer/](#agentanalyzer)
   - [agent/rules/](#agentrules)
   - [agent/git/](#agentgit)
   - [agent/utils/](#agentutils)
7. [Rule System](#7-rule-system)
   - [Rule Schema](#rule-schema)
   - [Rule Types](#rule-types)
   - [Rule Files Reference](#rule-files-reference)
8. [Git Hook Integration](#8-git-hook-integration)
9. [Configuration](#9-configuration)
10. [Adding New Rules](#10-adding-new-rules)
11. [Adding a New Language](#11-adding-a-new-language)
12. [Remote Rules API](#12-remote-rules-api)
13. [Testing](#13-testing)
14. [CLI Reference](#14-cli-reference)

---

## 1. Project Overview

**Code Review Agent** is a Python-based intelligent code review gate that runs as a `git pre-commit` hook. It automatically inspects staged code changes before they are committed and blocks the commit if violations of your team's coding standards are found.

It is inspired by [Husky](https://typicode.github.io/husky/) but goes beyond simple linting hooks by:

- **Auto-detecting** the project language (Python, JavaScript, TypeScript) and framework (React, Next.js, FastAPI, Django, Express, React Native)
- **Loading rules dynamically** from JSON files based on the detected context
- **Using AST-based parsing** for Python files (not just regex), catching structural violations that regex cannot
- **Supporting a centralized rule API** so teams can distribute rules across repositories
- **Providing fix suggestions** for every violation directly in the terminal

### Key Design Goals

| Goal | How it is achieved |
|------|-------------------|
| Zero config for common projects | Auto-detection of language and framework |
| Extensible rule system | JSON rule files, one per language/framework |
| Deep Python analysis | `ast` module — no external parser needed |
| JS/TS analysis without native deps | Carefully constructed regex heuristics |
| Non-blocking warnings | Three severity levels: `error`, `warning`, `info` |
| Centralized governance | Optional remote rules API with local caching |

---

## 2. Folder Structure

```
code_review_agent/
│
├── main.py                        ← CLI entry point (called by installed hook)
├── setup.py                       ← Pip-installable package (exposes `cra` command)
├── requirements.txt               ← Runtime + dev dependencies
├── config.yaml                    ← Template project config
├── .env.example                   ← Environment variable reference
│
├── agent/                         ← All application source code
│   ├── __init__.py
│   ├── cli.py                     ← CLI argument parsing & dispatch
│   ├── hook_runner.py             ← Orchestrates a full review session
│   │
│   ├── detector/                  ← Project environment detection
│   │   ├── language_detector.py   ← Detects Python / JS / TS / Go …
│   │   ├── framework_detector.py  ← Detects React / FastAPI / Django …
│   │   └── project_context.py     ← Combines detections into one object
│   │
│   ├── analyzer/                  ← Language-specific code analysis
│   │   ├── base_analyzer.py       ← Abstract base class
│   │   ├── python_analyzer.py     ← Python AST checks (ast module)
│   │   ├── javascript_analyzer.py ← JS/TS heuristic checks
│   │   └── generic_analyzer.py    ← No-op fallback for other languages
│   │
│   ├── rules/                     ← Rule loading, validation, execution
│   │   ├── rule_loader.py         ← Loads & merges JSON rule files
│   │   ├── rule_validator.py      ← Validates rule schema on load
│   │   ├── rule_engine.py         ← Applies rules to file content
│   │   └── api_fetcher.py         ← Fetches rules from remote API
│   │
│   ├── git/                       ← Git integration
│   │   ├── git_utils.py           ← Collects files from push/stage
│   │   └── hook_installer.py      ← Installs / removes the hook script
│   │
│   └── utils/                     ← Shared utilities
│       ├── logger.py              ← Structured logging setup
│       ├── config_manager.py      ← Loads .code-review-agent.yaml
│       └── reporter.py            ← Colored terminal output
│
├── rules/                         ← Bundled JSON rule files
│   ├── common/
│   │   └── common_rules.json      ← Language-agnostic rules
│   ├── python/
│   │   ├── base_rules.json        ← PEP 8, AST checks
│   │   ├── fastapi_rules.json     ← FastAPI-specific
│   │   └── django_rules.json      ← Django-specific
│   ├── javascript/
│   │   ├── base_rules.json        ← JS fundamentals
│   │   ├── react_rules.json       ← React.js
│   │   ├── nextjs_rules.json      ← Next.js App Router
│   │   ├── nodejs_express_rules.json ← Node + Express
│   │   └── react_native_rules.json   ← React Native
│   └── typescript/
│       └── base_rules.json        ← TypeScript type safety
│
├── tests/                         ← Unit test suite (57 tests)
│   ├── test_detector.py
│   ├── test_analyzer.py
│   └── test_rule_engine.py
│
└── sample_files/                  ← Demo files with intentional violations
    ├── bad_python.py
    ├── bad_react.tsx
    └── bad_fastapi.py
```

---

## 3. Packages & Dependencies

### Runtime Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| **PyYAML** | `>=6.0` | Parses `.code-review-agent.yaml` config files |

That's it. The agent intentionally keeps runtime dependencies minimal.

### Standard Library Modules Used

These are built into Python 3.9+ — no installation required.

| Module | Used in | Purpose |
|--------|---------|---------|
| `ast` | `python_analyzer.py` | Parse Python source into an Abstract Syntax Tree for deep structural checks |
| `re` | `rule_engine.py`, `javascript_analyzer.py` | Regex pattern matching for all regex-type rules |
| `json` | `rule_loader.py`, `api_fetcher.py`, detectors | Parse JSON rule files and `package.json` |
| `subprocess` | `git_utils.py` | Execute `git` commands to get changed files |
| `pathlib` | Throughout | Cross-platform file path handling |
| `logging` | `logger.py` | Structured log output to stderr |
| `dataclasses` | `reporter.py`, `project_context.py` | Clean data container objects |
| `abc` | `base_analyzer.py` | Abstract base class for analyzer interface |
| `fnmatch` | `rule_engine.py` | File pattern exclusion matching (e.g. `*.test.*`) |
| `hashlib` | `api_fetcher.py` | Generates cache key for remote rule responses |
| `urllib.request` | `api_fetcher.py` | HTTP requests to remote rules API (no `requests` needed) |
| `stat` | `hook_installer.py` | Set executable bit on the hook script |
| `enum` | `reporter.py` | `Severity` enum (`error`, `warning`, `info`) |
| `sys` | Throughout | `sys.stdin` for hook input, `sys.exit` for exit codes |

### Development / Test Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| **pytest** | `>=7.4` | Test runner |
| **pytest-cov** | `>=4.1` | Code coverage reporting (optional) |

---

## 4. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      git pre-commit hook                    │
│                       (shell script)                        │
│                  calls: cra review --staged                 │
└─────────────────────┬───────────────────────────────────────┘
                      │ (staged files collected via git diff --cached)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                        cli.py  (cra)                        │
│              (parses command, dispatches to runner)          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                     hook_runner.py                          │
│                                                             │
│  1. ConfigManager   ← loads .code-review-agent.yaml        │
│  2. git_utils       ← collects changed file paths          │
│  3. ProjectContext  ← detects language + framework         │
│  4. RuleLoader      ← loads JSON rules for context         │
│  5. ApiFetcher      ← (optional) merges remote rules       │
│  6. LintRunner      ← runs ruff/flake8 or ESLint first     │
│  7. RuleEngine      ← applies rules to each file           │
│  8. Reporter        ← prints colored output                 │
│  9. exit(0 or 1)    ← 1 blocks the commit                  │
└─────────────────────────────────────────────────────────────┘

        ┌──────────────────┐    ┌──────────────────────────┐
        │  ProjectContext   │    │       RuleEngine          │
        │                  │    │                           │
        │ language=python  │    │  for each file:           │
        │ framework=fastapi│    │   • regex rules → re      │
        │ files=[...]      │    │   • ast rules →           │
        └──────────────────┘    │     PythonAnalyzer (ast)  │
                                │     JavaScriptAnalyzer    │
        ┌──────────────────┐    │   • filename rules → re   │
        │    RuleLoader    │    └──────────────────────────┘
        │                  │
        │ common_rules     │    ┌──────────────────────────┐
        │ + python/base    │    │        Reporter           │
        │ + fastapi_rules  │    │                           │
        └──────────────────┘    │  ✖ [ERROR]  L5  PY001    │
                                │  ⚠ [WARNING] L9  PY003   │
                                │                           │
                                │  🚫 Push BLOCKED          │
                                └──────────────────────────┘
```

---

## 5. End-to-End Flow

### Step-by-step walkthrough of a `git push`

```
Developer runs: git push origin feature/my-feature
                        │
                        ▼
        Git executes .git/hooks/pre-push
        Passes via stdin:
          "refs/heads/feature  abc123  refs/heads/main  def456"
                        │
                        ▼
        main.py  →  cli.py  →  hook_runner.run_review()
                        │
          ┌─────────────┼──────────────────────────────┐
          │             │                              │
          ▼             ▼                              ▼
   ConfigManager   git_utils                   ProjectContext
   loads config    git diff def456..abc123     LanguageDetector
   from yaml       returns changed files:      reads requirements.txt
                   ["app/routes.py",           → language = "python"
                    "app/schemas.py"]
                                               FrameworkDetector
                                               reads requirements.txt
                                               finds "fastapi"
                                               → framework = "fastapi"
                        │
                        ▼
                   RuleLoader
                   loads rules:
                     rules/common/common_rules.json      (6 rules)
                     rules/python/base_rules.json        (9 rules)
                     rules/python/fastapi_rules.json     (7 rules)
                   → 20 rules total (disabled ones excluded)
                        │
                        ▼
                   (Optional) ApiFetcher
                   GET https://rules.company.com/rules?language=python&framework=fastapi
                   merges any additional remote rules
                        │
                        ▼
                   RuleEngine.review_files(files, rules)
                        │
                   for each file (app/routes.py, app/schemas.py):
                     reads file content
                     for each rule:
                       if rule.type == "regex":
                         scan each line with re.search(pattern, line)
                       if rule.type == "ast":
                         PythonAnalyzer.run_ast_check(content, rule)
                           → ast.parse(content) builds syntax tree
                           → walk tree looking for violations
                       if rule.type == "filename":
                         re.search(pattern, file_path)
                     collect Violation objects
                        │
                        ▼
                   Reporter.print_result(result)
                   prints colored output to stdout
                        │
                        ├── violations with severity=error?
                        │     YES → exit(1)  ← git blocks the push
                        │     NO  → exit(0)  ← git allows the push
                        ▼
             Developer sees violations + fix suggestions
             and must fix them before the push succeeds
```

---

## 6. Module Reference

### main.py

**Role:** Single entry point for all operations.

Adds the project root to `sys.path` (so the `agent` package is importable regardless of where you run from), then delegates to `cli.run_cli()`.

```python
from agent.cli import run_cli
sys.exit(run_cli())
```

---

### agent/cli.py

**Role:** Parses `sys.argv` and dispatches to sub-commands.

No third-party CLI framework is used (avoids `click`/`argparse` dependency). Arguments are parsed with a simple `while` loop over `sys.argv`.

| Sub-command | What it does |
|-------------|--------------|
| `review` | Manual review of explicit files or auto-collected git files |
| `hook` | Called by the git hook — same as review but reads stdin refs |
| `install` | Installs `.git/hooks/pre-push` script |
| `uninstall` | Removes the hook |
| `rules` | Lists loaded rules for a given language/framework |

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | No blocking violations |
| `1` | Blocking violations found |
| `2` | Usage/configuration error |

---

### agent/hook_runner.py

**Role:** The main orchestrator. Called by both `review` and `hook` CLI commands.

```
run_review()
  │
  ├── ConfigManager(config_path)
  ├── get_repo_root() / collect_files_for_push() / get_staged_files()
  ├── build_project_context(root, files, language_override, framework_override)
  ├── Reporter.print_header()
  ├── RuleLoader.load_rules(language, framework)
  ├── ApiFetcher.fetch_rules()    ← only if remote_rules_url is set
  ├── RuleEngine(python_analyzer, js_analyzer)
  ├── engine.review_files(files, rules)
  ├── Reporter.print_result(result)
  └── return 0 or 1
```

**Key design:** Analyzers are injected into `RuleEngine` — this keeps the engine generic and makes testing easy (you can pass mock analyzers in tests).

---

### agent/detector/

#### language_detector.py

Detects the project's primary programming language using a priority-ordered strategy:

1. **Indicator files** — presence of `requirements.txt` → Python, `go.mod` → Go, etc.
2. **package.json content** — checks `devDependencies` for `typescript` to distinguish JS from TS
3. **File extension counting** — walks the project tree and votes by extension count
4. **Fallback** — returns `"unknown"`

```python
_INDICATOR_FILES = {
    "requirements.txt": "python",
    "setup.py": "python",
    "pyproject.toml": "python",
    "go.mod": "go",
    ...
}
```

Also provides `detect_file_language(file_path)` to determine language per individual file by extension.

#### framework_detector.py

Detects the framework using a priority-ordered strategy:

1. **Path-based** — presence of `manage.py` → Django, `next.config.js` → Next.js
2. **package.json deps** — checks `dependencies` + `devDependencies` in order (react-native before react, next before react to avoid misdetection)
3. **requirements.txt** — searches for `fastapi`, `django`, `flask`, etc.
4. **pyproject.toml** — same keyword search

```python
# Detection order matters — more specific frameworks first
_JS_FRAMEWORK_DEPS = {
    "react-native": "react_native",  # before "react"
    "next": "nextjs",                # before "react"
    "react": "react",
    "express": "express",
    ...
}
```

#### project_context.py

Combines language + framework into a `ProjectContext` dataclass:

```python
@dataclass
class ProjectContext:
    language: str           # e.g. "python"
    framework: Optional[str] # e.g. "fastapi"
    project_root: str
    files_to_review: List[str]
```

Helper properties: `is_typescript`, `is_javascript_family`, `is_python_family`.

---

### agent/analyzer/

#### base_analyzer.py

Abstract base class enforcing the analyzer interface:

```python
class BaseAnalyzer(ABC):
    @abstractmethod
    def run_ast_check(
        self, file_path, content, rule, ast_check
    ) -> List[Violation]: ...
```

#### python_analyzer.py

Uses Python's built-in `ast` module to build a syntax tree and walk it for violations. No third-party parser needed.

| `ast_check` value | What it inspects | AST node type |
|-------------------|-----------------|---------------|
| `bare_except` | `except:` with no exception type | `ast.ExceptHandler` |
| `wildcard_import` | `from x import *` | `ast.ImportFrom` |
| `print_usage` | `print()` calls | `ast.Call` |
| `eval_exec_usage` | `eval()` / `exec()` calls | `ast.Call` |
| `missing_type_hints` | Functions missing annotations | `ast.FunctionDef` |
| `snake_case_functions` | Non-snake_case function names | `ast.FunctionDef` |
| `no_unused_imports` | Imported names never referenced | `ast.Import` + `ast.Name` |

**How AST analysis works:**

```python
tree = ast.parse(content, filename=file_path)

for node in ast.walk(tree):
    if isinstance(node, ast.ExceptHandler):
        if node.type is None:          # bare except
            violations.append(...)
```

`ast.walk()` recursively visits every node in the tree. Each check inspects specific node types and their attributes.

#### javascript_analyzer.py

Since Python cannot natively parse JavaScript ASTs without compiled extensions (tree-sitter), this analyzer uses carefully constructed regex patterns applied line-by-line to approximate structural checks.

| `ast_check` value | Detection method |
|-------------------|-----------------|
| `no_class_components` | Regex: `class X extends React.Component` |
| `no_console_log` | Regex on non-comment lines: `console.(log\|warn\|error)(` |
| `no_var_declaration` | Regex: `\bvar\s+\w+` |
| `no_inline_styles` | Regex: `style=\{\{` |
| `no_async_storage_secrets` | Regex: `AsyncStorage.setItem('token'...)` |
| `no_jwt_in_localstorage` | Regex: `localStorage.setItem('token'...)` |
| `no_any_type` | Regex: `:\s*any\b` |
| `use_flatlist` | Checks if `.map(` used without FlatList/SectionList in file |
| `no_raw_anchor` | Regex: `<a\s[^>]*href=[\"']/` |

#### generic_analyzer.py

A no-op fallback for languages without a dedicated analyzer. The `RuleEngine` still applies regex rules to these files — only AST-type rules are skipped.

---

### agent/rules/

#### rule_loader.py

Loads and merges JSON rule files in a fixed priority order:

```
1. rules/common/common_rules.json          ← always loaded
2. rules/<language>/base_rules.json        ← e.g. rules/python/base_rules.json
3. rules/<language>/<framework>_rules.json ← e.g. rules/python/fastapi_rules.json
```

TypeScript projects also load `rules/javascript/base_rules.json` because TS is a superset of JS.

**Deduplication:** If the same rule `id` appears in multiple files (e.g. a common rule and a language rule both define `COM001`), only the first occurrence is kept.

**Disabled rules** (`"enabled": false`) are filtered out at load time.

#### rule_validator.py

Validates every rule dictionary on load. Checks:
- All required fields are present (`id`, `name`, `severity`, `type`, `message`)
- `severity` is one of `error`, `warning`, `info`
- `type` is one of `regex`, `ast`, `filename`
- `regex` rules have a `pattern` field
- `ast` rules have an `ast_check` field
- No duplicate `id` values within one file

Validation warnings are logged but do not crash the agent.

#### rule_engine.py

The execution core. For each file × each rule:

```
if rule.type == "regex":
    compile pattern with re.compile()
    scan each line → collect matches as Violation objects

if rule.type == "ast":
    if file is .py → delegate to PythonAnalyzer.run_ast_check()
    if file is .js/.ts/.jsx/.tsx → delegate to JavaScriptAnalyzer.run_ast_check()
    if no analyzer → try rule's fallback_pattern as regex

if rule.type == "filename":
    re.search(pattern, file_path)
    compare match result vs rule's expect_match flag
```

Also handles:
- **Extension filtering** — `file_extensions: [".py"]` skips non-matching files
- **Exclude patterns** — `exclude_file_patterns: ["test_*.py"]` skips test files
- **File size limit** — files over `max_file_size_kb` are skipped
- **Exclude paths** — `node_modules`, `venv`, etc. are never scanned

#### api_fetcher.py

Fetches additional rules from a remote HTTP endpoint.

```
GET https://rules.yourcompany.com/rules?language=python&framework=fastapi
Authorization: Bearer <token>

Response: { "rules": [ {...}, {...} ] }
```

**Caching:** Responses are cached in `~/.cache/code_review_agent/remote_rules/` for 1 hour to avoid network delays on every push. Cache key is an MD5 hash of `language_framework`.

---

### agent/git/

#### git_utils.py

Provides two file-collection modes:

**Pre-push mode** (default):

```python
# Git provides via stdin:
# "refs/heads/feature abc123 refs/heads/main def456"

git diff --name-only --diff-filter=ACMRT def456..abc123
# Returns: files changed between remote SHA and local SHA
```

Special case — new branch (remote SHA is all zeros):
```python
git merge-base abc123 origin/main
# Uses the merge-base commit instead of zero SHA
```

**Staged mode** (`--staged` flag):
```python
git diff --cached --name-only --diff-filter=ACMRT
```

`--diff-filter=ACMRT` means only Added, Copied, Modified, Renamed, Type-changed files (excludes Deleted).

#### hook_installer.py

Writes a shell script to `.git/hooks/pre-push`:

```bash
#!/bin/sh
PYTHON="/path/to/venv/python"
AGENT="/path/to/main.py"
"$PYTHON" "$AGENT" hook "$@"
exit $?
```

The script uses the absolute path of the venv Python so the hook works regardless of the shell's active environment.

---

### agent/utils/

#### logger.py

Creates `logging.Logger` instances that write to `stderr` (so stdout stays clean for the reporter output). Log level is set globally via `ConfigManager.log_level`.

```python
logger = get_logger(__name__)
logger.debug("Detected language: python")
logger.warning("Could not parse package.json: ...")
```

#### config_manager.py

Searches for a config file in order:
1. Explicit path passed via `--config`
2. `.code-review-agent.yaml`
3. `.code-review-agent.yml`
4. `code_review_agent.yaml`
5. `code_review_config.yaml`

Falls back to hardcoded defaults if no file is found. PyYAML is only imported if a config file exists, so the agent works without it.

#### reporter.py

Builds and prints colored terminal output using ANSI escape codes (no `colorama` or `rich` needed). On Windows, `sys.stdout.reconfigure(encoding="utf-8")` is called to support Unicode characters.

**Violation display format:**
```
📄 path/to/file.py
  ✖ [ERROR  ]   L5  PY001 — Wildcard import 'os.path' pollutes the namespace.
             → from os.path import *
             Fix: Replace with explicit imports.
```

---

## 7. Rule System

### Rule Schema

Every rule in a JSON file has this structure:

```json
{
  "id": "PY001",
  "name": "no_wildcard_imports",
  "description": "Human-readable description",
  "severity": "error",
  "category": "style",
  "type": "regex",
  "pattern": "^from\\s+\\S+\\s+import\\s+\\*",
  "message": "Shown in the terminal when violated",
  "fix_suggestion": "Shown below the violation",
  "file_extensions": [".py"],
  "exclude_file_patterns": ["test_*.py"],
  "enabled": true
}
```

| Field | Required | Values | Description |
|-------|----------|--------|-------------|
| `id` | ✅ | String | Unique rule identifier |
| `name` | ✅ | String | Machine-readable name |
| `severity` | ✅ | `error` \| `warning` \| `info` | `error` blocks push |
| `type` | ✅ | `regex` \| `ast` \| `filename` | Rule execution strategy |
| `message` | ✅ | String | Shown in terminal output |
| `description` | ❌ | String | Documentation only |
| `category` | ❌ | String | Grouping label |
| `pattern` | ✅ for regex | Regex string | Pattern to search per line |
| `ast_check` | ✅ for ast | String | Named check in the analyzer |
| `expect_match` | ❌ | `true`/`false` | For filename rules: whether match = violation |
| `fix_suggestion` | ❌ | String | How to fix the violation |
| `file_extensions` | ❌ | `[".py"]` | Limit rule to these extensions |
| `exclude_file_patterns` | ❌ | `["*.test.*"]` | Skip files matching these globs |
| `fallback_pattern` | ❌ | Regex string | Regex fallback when AST unavailable |
| `enabled` | ❌ | `true`/`false` | Set `false` to disable without deleting |
| `case_insensitive` | ❌ | `true`/`false` | Apply `re.IGNORECASE` to regex |

### Rule Types

#### `regex` — Line-by-line pattern matching

```json
{
  "type": "regex",
  "pattern": "\\beval\\s*\\(",
  "file_extensions": [".py"]
}
```

The engine iterates every line of the file and calls `re.search(pattern, line)`. If matched, a `Violation` is created with the line number and the full line as the snippet.

#### `ast` — Deep structural analysis

```json
{
  "type": "ast",
  "ast_check": "bare_except",
  "fallback_pattern": "except\\s*:"
}
```

The engine delegates to the language-specific analyzer. If no analyzer is available for the file type, `fallback_pattern` is used as a regex instead.

#### `filename` — Path convention enforcement

```json
{
  "type": "filename",
  "pattern": "(^|/)\\.env(\\.local)?$",
  "expect_match": false
}
```

`expect_match: false` means the violation is triggered *when the pattern matches* the file path — blocking `.env` files from being pushed.

### Rule Files Reference

| File | Rule IDs | Coverage |
|------|----------|----------|
| `common/common_rules.json` | COM001–COM006 | Secrets, TODO, debugger, URLs, conflict markers, .env |
| `python/base_rules.json` | PY001–PY010 | Wildcard imports, bare except, print, eval, type hints, snake_case, unused imports, line length, secrets |
| `python/fastapi_rules.json` | FAPI001–FAPI007 | Async routes, path casing, Pydantic models, CORS, HTTPException, APIRouter |
| `python/django_rules.json` | DJ001–DJ005 | DEBUG, SECRET_KEY, ALLOWED_HOSTS, raw SQL, N+1 |
| `javascript/base_rules.json` | JS001–JS007 | console, var, strict equality, secrets, quotes, semicolons, async/await |
| `javascript/react_rules.json` | REACT001–REACT008 | Class components, raw anchor, inline styles, JWT localStorage, ErrorBoundary, global CSS, lazy load, hardcoded routes |
| `javascript/nextjs_rules.json` | NEXT001–NEXT007 | next/link, next/image, secrets, server components, dynamic imports, pages/api, next/navigation |
| `javascript/nodejs_express_rules.json` | NODE001–NODE007 | console, route casing, validation, secrets, async/await, error exposure, sanitization |
| `javascript/react_native_rules.json` | RN001–RN007 | Inline styles, AsyncStorage secrets, FlatList, SafeAreaView, Platform styles, class components, lazy modules |
| `typescript/base_rules.json` | TS001–TS006 | any type, return types, null/undefined, Id suffix, prop types, non-null assertion |

---

## 8. Git Hook Integration

### How the hook is installed

Running `cra install` (or `cra install --repo /path/to/repo`) writes this file to `.git/hooks/pre-commit`:

```bash
#!/bin/sh
# Code Review Agent — pre-commit hook
PYTHON="/absolute/path/to/venv/Scripts/python"
AGENT="/absolute/path/to/agent/cli.py"
"$PYTHON" "$AGENT" review --staged
exit $?
```

The hook is made executable (`chmod +x`).

### How staged files are collected

The agent runs `git diff --cached --name-only --diff-filter=ACM` to collect only the files staged for the current commit. It does not inspect unstaged or untracked files.

### Exit code semantics

| Exit code | Effect |
|-----------|--------|
| `0` | Git proceeds with the commit |
| Non-zero (`1`) | Git aborts the commit — developer must fix violations and re-stage |

---

## 9. Configuration

Copy `config.yaml` to your project root as `.code-review-agent.yaml` and customize:

```yaml
# Block push on error-severity violations (recommended: true)
block_on_error: true

# Also block on warnings (stricter mode)
block_on_warning: false

# Log level: DEBUG | INFO | WARNING | ERROR
log_level: WARNING

# Custom rules directory (null = use bundled rules/)
rules_dir: null

# Centralized rule API
remote_rules_url: null
remote_rules_token: null

# Paths to skip entirely
exclude_paths:
  - node_modules
  - __pycache__
  - venv
  - .venv
  - dist
  - build
  - migrations

# Max file size to analyse
max_file_size_kb: 500
```

Environment variables:
- `REVIEW_RULES_API_URL` — overrides `remote_rules_url`
- `REVIEW_RULES_API_TOKEN` — overrides `remote_rules_token`

---

## 10. Adding New Rules

### Add a regex rule

Edit the appropriate JSON file (e.g. `rules/python/base_rules.json`) and add to the `rules` array:

```json
{
  "id": "PY011",
  "name": "no_assert_in_production",
  "description": "assert statements are removed with -O and should not guard production logic",
  "severity": "warning",
  "category": "correctness",
  "type": "regex",
  "pattern": "^\\s*assert\\s+",
  "message": "assert statement found. Do not use assert for production input validation.",
  "fix_suggestion": "Replace with an explicit if check and raise an appropriate exception.",
  "file_extensions": [".py"],
  "exclude_file_patterns": ["test_*.py", "*_test.py"],
  "enabled": true
}
```

**Rule ID convention:**

| Prefix | Scope |
|--------|-------|
| `COM` | Common (all languages) |
| `PY` | Python |
| `FAPI` | FastAPI |
| `DJ` | Django |
| `JS` | JavaScript base |
| `REACT` | React.js |
| `NEXT` | Next.js |
| `NODE` | Node.js/Express |
| `RN` | React Native |
| `TS` | TypeScript |

### Add an AST rule (Python)

1. Add the rule to a JSON file with `"type": "ast"` and a new `"ast_check"` name:

```json
{
  "id": "PY012",
  "name": "no_mutable_default_args",
  "severity": "error",
  "type": "ast",
  "ast_check": "mutable_default_args",
  "message": "Mutable default argument (list/dict) detected — shared across calls.",
  "fix_suggestion": "Use None as default and initialise inside the function body.",
  "file_extensions": [".py"]
}
```

2. Add the check method to `agent/analyzer/python_analyzer.py`:

```python
# In PythonAnalyzer._CHECK_DISPATCH:
"mutable_default_args": "_check_mutable_default_args",

# New method:
def _check_mutable_default_args(self, tree, file_path, content, lines, rule):
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for default in node.args.defaults:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    violations.append(_make_violation(rule, file_path, node.lineno))
    return violations
```

---

## 11. Adding a New Language

Example: adding **Go** support.

1. Create `rules/go/base_rules.json` with Go-specific rules.

2. Add Go extensions to `agent/detector/language_detector.py`:
```python
_EXT_LANGUAGE[".go"] = "go"
```

3. Create `agent/analyzer/go_analyzer.py` implementing `BaseAnalyzer` (or reuse `GenericAnalyzer` for regex-only rules).

4. Register the analyzer in `agent/hook_runner.py`:
```python
go_analyzer = GoAnalyzer()
engine = RuleEngine(python_analyzer=py_analyzer, js_analyzer=js_analyzer, go_analyzer=go_analyzer)
```

5. Update `RuleEngine` to dispatch `.go` files to the Go analyzer.

---

## 12. Remote Rules API

Set in config:
```yaml
remote_rules_url: https://rules.yourcompany.com/api/v1
remote_rules_token: ${REVIEW_RULES_API_TOKEN}
```

Expected API contract:

```
GET /rules?language=python&framework=fastapi
Authorization: Bearer <token>

200 OK
Content-Type: application/json

{
  "version": "1.0",
  "rules": [
    {
      "id": "CUSTOM001",
      "name": "company_specific_rule",
      "severity": "error",
      "type": "regex",
      "pattern": "internal_api\\.do_dangerous_thing",
      "message": "...",
      ...
    }
  ]
}
```

Remote rules are merged after local rules. If a remote rule has the same `id` as a local rule, the local rule wins.

Cache location: `~/.cache/code_review_agent/remote_rules/`
Cache TTL: 1 hour (configurable in `api_fetcher.py`)

---

## 13. Testing

### Run the test suite

```bash
# Activate venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=agent --cov-report=term-missing
```

### Test coverage

| Test file | What is tested |
|-----------|---------------|
| `test_detector.py` | Language detection by file indicators and extension counting; framework detection by package.json, requirements.txt, path |
| `test_analyzer.py` | Every AST check in `PythonAnalyzer`; every heuristic check in `JavaScriptAnalyzer`; edge cases (syntax errors, comments, correct code) |
| `test_rule_engine.py` | Rule validation schema; rule loading and merging; engine execution (regex violations, extension filter, exclude paths, disabled rules, file counter, severity blocking) |

### Test design principles

- **No mocks** — tests write real temp files and run real logic
- **Positive + negative cases** — every test has a "bad code" case and a "correct code" case
- **Edge cases** — syntax errors, comment lines, empty files are handled gracefully

---

## 14. CLI Reference

The agent is installed as a global `cra` command via pip:

```bash
pip install -e /path/to/code_review_agent
# or org-wide:
pip install git+https://github.com/your-org/code-review-agent.git
```

```
cra <command> [options]
```

### `review` — Manual review

```bash
cra review [--staged] [--dir PATH] [--lang LANG] [--framework FW] [--config PATH] [FILE ...]

# Examples:
cra review --dir /path/to/project              # auto-scan entire project directory
cra review --staged                            # review only staged files (pre-commit mode)
cra review --lang python --dir /path/to/proj  # override language detection
cra review --lang javascript --framework react src/
cra review --config myconfig.yaml
```

### `install` — Install the pre-commit hook

```bash
cra install                              # install into current git repo
cra install --force                      # overwrite existing hook
cra install --repo /path/to/other/repo   # install into a different repo
```

### `uninstall` — Remove the pre-commit hook

```bash
cra uninstall
cra uninstall --repo /path/to/other/repo
```

### `rules` — List loaded rules

```bash
cra rules --lang python --framework fastapi
cra rules --lang javascript --framework react
cra rules --lang typescript
```

---

*Documentation generated for Code Review Agent v1.0.0 — Python 3.11*