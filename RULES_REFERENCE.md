# Rules Reference Guide

**Audience:** Developers adding or modifying rules
**Location:** `rules/` directory (JSON files)
**Updated:** March 2026

---

## Table of Contents

1. [Rule File Structure](#1-rule-file-structure)
2. [File-Level Keys](#2-file-level-keys)
3. [Rule-Level Keys — Complete Reference](#3-rule-level-keys--complete-reference)
4. [Rule Types Explained](#4-rule-types-explained)
5. [Severity Levels](#5-severity-levels)
6. [Categories Reference](#6-categories-reference)
7. [AST Check Values](#7-ast-check-values)
8. [File Organisation](#8-file-organisation)
9. [All Existing Rules](#9-all-existing-rules)
10. [Writing a New Rule — Examples](#10-writing-a-new-rule--examples)

---

## 1. Rule File Structure

Every rule file is a `.json` file with this top-level shape:

```json
{
  "version": "1.0.0",
  "language": "python",
  "framework": "fastapi",
  "description": "Human-readable description of this file",
  "rules": [ ...array of rule objects... ]
}
```

The `rules` array is what the engine reads. Everything else is metadata.

---

## 2. File-Level Keys

| Key | Required | Description | Example values |
|---|---|---|---|
| `version` | Yes | Schema version of this rule file | `"1.0.0"` |
| `language` | No | Language this file targets. Omit for common rules | `"python"`, `"javascript"`, `"typescript"` |
| `framework` | No | Framework this file targets. Omit for base rules | `"fastapi"`, `"react"`, `"express"` |
| `description` | Yes | One-line description shown in logs | `"Base Python rules derived from PEP 8"` |
| `rules` | Yes | Array of rule objects (see Section 3) | `[{...}, {...}]` |

---

## 3. Rule-Level Keys — Complete Reference

### `id`
| | |
|---|---|
| **Required** | Yes |
| **Type** | String |
| **Why it exists** | Unique identifier for the rule. Used in output, deduplication, and future config-based suppression |
| **Naming convention** | `PREFIX` + 3-digit number. Prefix matches the file: `COM` = common, `PY` = python, `JS` = javascript, `TS` = typescript, `FAPI` = fastapi, `REACT` = react, `NEXT` = nextjs, `NODE` = nodejs, `RN` = react native, `DJ` = django |
| **Possible values** | `"COM001"`, `"PY004"`, `"FAPI002"`, `"REACT005"` |

---

### `name`
| | |
|---|---|
| **Required** | Yes |
| **Type** | String |
| **Why it exists** | Machine-readable slug shown in verbose logs. Should describe what the rule *prevents* |
| **Convention** | `snake_case`, starts with `no_` for prohibitions or a noun for requirements |
| **Possible values** | `"no_hardcoded_secrets"`, `"snake_case_function_names"`, `"async_route_handlers"` |

---

### `description`
| | |
|---|---|
| **Required** | Yes |
| **Type** | String |
| **Why it exists** | Full explanation of *why* this rule exists — shown in documentation and debug logs |
| **Possible values** | Any plain English string explaining the problem the rule prevents |

---

### `severity`
| | |
|---|---|
| **Required** | Yes |
| **Type** | String (enum) |
| **Why it exists** | Controls whether a violation blocks the commit or just warns |
| **Possible values** | See table below |

| Value | Effect on commit | When to use |
|---|---|---|
| `"error"` | **Blocks commit** | Security issues, broken code, conflict markers |
| `"warning"` | Commit allowed, violation shown | Style issues, recommended practices |
| `"info"` | Commit allowed, note shown | Suggestions, optional best practices |

---

### `category`
| | |
|---|---|
| **Required** | Yes |
| **Type** | String |
| **Why it exists** | Groups rules by concern for filtering and reporting. Not enforced by the engine — purely informational |
| **Possible values** | `"security"`, `"style"`, `"performance"`, `"error_handling"`, `"logging"`, `"type_safety"`, `"dead_code"`, `"maintainability"`, `"api_design"`, `"architecture"`, `"documentation"`, `"correctness"`, `"safety"`, `"debug"` |

---

### `type`
| | |
|---|---|
| **Required** | Yes |
| **Type** | String (enum) |
| **Why it exists** | Tells the engine *how* to evaluate this rule |
| **Possible values** | `"regex"`, `"ast"`, `"filename"` |

> See **Section 4** for a full explanation of each type.

---

### `pattern`
| | |
|---|---|
| **Required** | Required when `type` is `"regex"` or `"filename"` |
| **Type** | String (regex) |
| **Why it exists** | The regex the engine runs against file content (for `regex` type) or the file path (for `filename` type) |
| **Important** | JSON requires backslashes to be escaped: `\b` becomes `\\b`, `\s` becomes `\\s` |
| **Example** | `"\\b(eval|exec)\\s*\\("` matches `eval(` or `exec(` |

---

### `expect_match`
| | |
|---|---|
| **Required** | Only for `type: "filename"` rules |
| **Type** | Boolean |
| **Why it exists** | For filename rules, controls when the violation triggers |
| **Possible values** | |

| Value | Meaning | Use case |
|---|---|---|
| `true` (default) | Violation fires when the filename **does NOT match** the pattern | Enforce naming conventions (e.g. all controllers must end in `Controller.js`) |
| `false` | Violation fires when the filename **does match** the pattern | Block specific files (e.g. `.env`, `credentials.json`) |

**Example — blocking `.env` files:**
```json
{
  "type": "filename",
  "pattern": "(^|/)\\.env(\\.local|\\.production)?$",
  "expect_match": false
}
```
The violation triggers *when the pattern matches* — i.e. when someone stages a `.env` file.

---

### `ast_check`
| | |
|---|---|
| **Required** | Required when `type` is `"ast"` |
| **Type** | String (enum) |
| **Why it exists** | Names the specific AST analysis function to run. AST checks are more accurate than regex because they understand code structure, not just text |
| **Possible values** | See **Section 7** |

---

### `fallback_pattern`
| | |
|---|---|
| **Required** | No |
| **Type** | String (regex) |
| **Why it exists** | When `type` is `"ast"`, the agent first tries the AST check. If the file can't be parsed (syntax error, wrong Python version), it falls back to this regex pattern as a safety net |
| **When to add it** | Always add one for `ast` rules — it ensures the rule still catches violations in unparseable files |
| **Example** | `"\\beval\\s*\\("` as fallback for the `eval_exec_usage` AST check |

---

### `message`
| | |
|---|---|
| **Required** | Yes |
| **Type** | String |
| **Why it exists** | The violation message shown to the developer in the terminal output |
| **Best practice** | One sentence. Start with what was found, not "you must". Be specific |
| **Example** | `"eval()/exec() detected — security risk. Never use with untrusted input."` |

---

### `fix_suggestion`
| | |
|---|---|
| **Required** | Yes (strongly recommended) |
| **Type** | String |
| **Why it exists** | Shown below the violation message. Tells the developer exactly how to fix it |
| **Best practice** | Include a concrete code example where possible |
| **Example** | `"Replace 'from module import *' with explicit imports: from module import ClassName"` |

---

### `file_extensions`
| | |
|---|---|
| **Required** | Yes (use empty array `[]` for all files) |
| **Type** | Array of strings |
| **Why it exists** | Limits which file types this rule applies to. Prevents Python rules running on JS files, etc. |
| **Possible values** | `[".py"]`, `[".js", ".jsx", ".ts", ".tsx"]`, `[]` (all files) |

---

### `exclude_file_patterns`
| | |
|---|---|
| **Required** | No |
| **Type** | Array of glob strings |
| **Why it exists** | Skips files matching these patterns. Used to avoid false positives in test files, example configs, or generated files |
| **Possible values** | `["*.test.*", "*.spec.*"]`, `["test_*.py", "conftest.py"]`, `["*.example", "*.md"]` |
| **Pattern matching** | Uses `fnmatch` — `*` matches anything, `?` matches one character |

---

### `enabled`
| | |
|---|---|
| **Required** | Yes |
| **Type** | Boolean |
| **Why it exists** | Lets rules ship in the file but be turned off by default. Useful for rules that are too noisy or team-preference-dependent |
| **Possible values** | `true` — rule is active. `false` — rule is loaded but skipped |
| **Example use** | `PY008` (max line length) is `false` by default because teams use different limits |

---

### `comment`
| | |
|---|---|
| **Required** | No |
| **Type** | String |
| **Why it exists** | Internal note for rule authors. Explains *why* a rule is disabled, or limitations of the implementation. Not shown to developers |
| **Example** | `"Disabled by default — many teams use 88 or 120. Enable in config to enforce."` |

---

### `case_insensitive`
| | |
|---|---|
| **Required** | No |
| **Type** | Boolean |
| **Why it exists** | Makes the `pattern` regex case-insensitive without using Python-style `(?i)` flags (which are invalid in JavaScript regex) |
| **Possible values** | `true`, `false` (default) |
| **When to use** | Use this instead of `(?i)` in your pattern — the engine handles the flag correctly for both Python and JS |

---

## 4. Rule Types Explained

### `"type": "regex"`
The engine runs the `pattern` against each **line** of the file.
- A match on any line = one violation reported at that line number
- Fast, works on all file types
- Limited: cannot understand code structure, may false-positive on comments or strings

```json
{
  "type": "regex",
  "pattern": "\\b(eval|exec)\\s*\\("
}
```

---

### `"type": "ast"`
The engine parses the file into an Abstract Syntax Tree and runs a named structural check.
- Much more accurate — understands context (e.g. only flags functions, not comments)
- Python only (uses Python's built-in `ast` module)
- Requires `ast_check` to be set
- Should always have a `fallback_pattern` for when parsing fails

```json
{
  "type": "ast",
  "ast_check": "bare_except",
  "fallback_pattern": "except\\s*:"
}
```

---

### `"type": "filename"`
The engine runs the `pattern` against the **file path**, not its content.
- Used to block or require specific file names
- Works regardless of file content
- Always pair with `expect_match` (see Section 3)

```json
{
  "type": "filename",
  "pattern": "(^|/)\\.env$",
  "expect_match": false
}
```

---

## 5. Severity Levels

```
Developer stages files
        │
        ▼
Agent runs all applicable rules
        │
        ├── 🔴 error found   ──► Commit BLOCKED
        │                         Developer must fix and re-stage
        │
        ├── 🟡 warning found  ──► Commit ALLOWED
        │                         Warning shown, developer may fix later
        │
        └── 🔵 info found     ──► Commit ALLOWED
                                  Note shown, purely informational
```

---

## 6. Categories Reference

| Category | What it covers | Typical severity |
|---|---|---|
| `security` | Secrets, credentials, dangerous functions | `error` |
| `safety` | Merge conflicts, data loss risks | `error` |
| `debug` | Breakpoints, debugger statements | `error` |
| `error_handling` | Bare except, unhandled errors | `error` or `warning` |
| `style` | Naming, quotes, line length, formatting | `warning` or `info` |
| `logging` | Console.log, print statements | `warning` |
| `type_safety` | Missing type hints, `any` type | `warning` |
| `dead_code` | Unused imports, unreachable code | `warning` |
| `maintainability` | Hardcoded URLs, magic numbers | `warning` |
| `performance` | Sync in async, missing pagination | `warning` |
| `api_design` | Route naming, Pydantic models, CORS | `warning` |
| `correctness` | Loose equality, wrong operator usage | `warning` |
| `architecture` | File structure, module organisation | `info` |
| `documentation` | Missing docstrings | `info` |

---

## 7. AST Check Values

These are the valid values for `ast_check` (Python only):

| Value | What it checks | Rule that uses it |
|---|---|---|
| `wildcard_import` | `from module import *` statements | PY001 |
| `bare_except` | `except:` with no exception type | PY002 |
| `print_usage` | Any `print()` call | PY003 |
| `eval_exec_usage` | `eval()` or `exec()` calls | PY004 |
| `missing_type_hints` | Public functions without type annotations | PY005 |
| `snake_case_functions` | Function names not in `snake_case` | PY006 |
| `no_unused_imports` | Imports that are never referenced | PY007 |
| `no_console_log` | `console.log/warn/error` (JS — regex fallback used) | JS001 |
| `no_var_declaration` | `var` keyword (JS — regex fallback used) | JS002 |

> **Note:** JS AST checks are regex-based fallbacks since the agent does not include a JS parser.
> Adding a new AST check requires adding code to `agent/analyzer/python_analyzer.py`.

---

## 8. File Organisation

```
rules/
├── common/
│   └── common_rules.json        ← Loaded for ALL projects regardless of language
│
├── python/
│   ├── base_rules.json          ← Loaded for all Python projects
│   ├── fastapi_rules.json       ← Loaded when framework = fastapi
│   └── django_rules.json        ← Loaded when framework = django
│
├── javascript/
│   ├── base_rules.json          ← Loaded for all JS/TS projects
│   ├── react_rules.json         ← Loaded when framework = react
│   ├── nextjs_rules.json        ← Loaded when framework = nextjs
│   ├── nodejs_express_rules.json← Loaded when framework = express
│   └── react_native_rules.json  ← Loaded when framework = react_native
│
└── typescript/
    └── base_rules.json          ← Loaded for all TypeScript projects (on top of JS base)
```

**Load order for a FastAPI project:**
```
common/common_rules.json  →  python/base_rules.json  →  python/fastapi_rules.json
```

Rules are merged — later files add to earlier ones, never override them.
Duplicate `id` values are silently skipped (first one wins).

---

## 9. All Existing Rules

### Common Rules (all projects)

| ID | Name | Severity | Type | What it catches |
|---|---|---|---|---|
| COM001 | no_hardcoded_secrets | error | regex | API keys, passwords, tokens in code |
| COM002 | no_todo_fixme_in_push | warning | regex | TODO/FIXME/HACK comments |
| COM003 | no_debug_breakpoints | error | regex | `debugger`, `pdb.set_trace`, `breakpoint()` |
| COM004 | no_hardcoded_urls | warning | regex | Raw HTTP URLs that should be in config |
| COM005 | no_merge_conflict_markers | error | regex | `<<<<<<<`, `>>>>>>>`, `=======` |
| COM006 | no_env_file_committed | error | filename | `.env` files staged for commit |

### Python Base Rules

| ID | Name | Severity | Type | What it catches |
|---|---|---|---|---|
| PY001 | no_wildcard_imports | error | ast | `from module import *` |
| PY002 | no_bare_except | error | ast | `except:` with no type |
| PY003 | no_print_statements | warning | ast | `print()` in backend code |
| PY004 | no_eval_exec | error | ast | `eval()` and `exec()` |
| PY005 | type_hints_required | warning | ast | Functions missing type annotations |
| PY006 | snake_case_function_names | warning | ast | camelCase function names |
| PY007 | no_unused_imports | warning | ast | Imports never used |
| PY008 | max_line_length_79 | warning | regex | Lines over 79 chars *(disabled by default)* |
| PY009 | no_hardcoded_secrets_python | error | regex | `SECRET_KEY`, `JWT_SECRET` assignments |
| PY010 | import_order | info | regex | Import ordering *(disabled by default)* |

### Python FastAPI Rules

| ID | Name | Severity | Type | What it catches |
|---|---|---|---|---|
| FAPI001 | async_route_handlers | warning | regex | `def` instead of `async def` in routes |
| FAPI002 | route_path_lowercase | warning | regex | Uppercase letters in route paths |
| FAPI003 | route_docstring_required | info | regex | Missing docstrings on routes *(disabled)* |
| FAPI004 | use_pydantic_models | warning | regex | `dict` used instead of Pydantic model |
| FAPI005 | explicit_cors_configuration | warning | regex | `allow_origins=['*']` in production |
| FAPI006 | http_exception_usage | warning | regex | Non-HTTP exceptions raised in routes |
| FAPI007 | feature_based_routers | info | regex | Routes defined directly on `app` in main.py |

### JavaScript Base Rules

| ID | Name | Severity | Type | What it catches |
|---|---|---|---|---|
| JS001 | no_console_statements | warning | ast | `console.log/warn/error` |
| JS002 | no_var_declarations | warning | ast | `var` keyword |
| JS003 | use_strict_equality | warning | regex | `==` and `!=` instead of `===` / `!==` |
| JS004 | no_hardcoded_secrets_js | error | regex | API keys and secrets in JS/TS |
| JS005 | double_quotes_strings | info | regex | Single-quoted strings *(disabled by default)* |
| JS006 | semicolons_required | info | regex | Missing semicolons *(disabled by default)* |
| JS007 | async_await_over_then | info | regex | `.then()` chains instead of async/await |

---

## 10. Writing a New Rule — Examples

### Example A — Block a specific file pattern (filename rule)

Prevent `credentials.json` from being committed:

```json
{
  "id": "COM007",
  "name": "no_credentials_json",
  "description": "Block credentials.json files from being committed",
  "severity": "error",
  "category": "security",
  "type": "filename",
  "pattern": "(^|/)credentials\\.json$",
  "expect_match": false,
  "message": "credentials.json detected. This file likely contains sensitive keys.",
  "fix_suggestion": "Add credentials.json to .gitignore and use environment variables instead.",
  "file_extensions": [],
  "enabled": true
}
```

---

### Example B — Catch a bad code pattern (regex rule)

Warn when `setTimeout` is used with a string argument (security/correctness issue):

```json
{
  "id": "JS008",
  "name": "no_settimeout_string",
  "description": "setTimeout with a string argument evaluates code like eval()",
  "severity": "error",
  "category": "security",
  "type": "regex",
  "pattern": "setTimeout\\s*\\(\\s*['\"`]",
  "message": "setTimeout() called with a string — this behaves like eval() and is a security risk.",
  "fix_suggestion": "Pass a function reference instead: setTimeout(() => doSomething(), 1000)",
  "file_extensions": [".js", ".jsx", ".ts", ".tsx"],
  "exclude_file_patterns": ["*.test.*", "*.spec.*"],
  "enabled": true
}
```

---

### Example C — Disable an existing rule

To turn off `PY003` (no print statements) just set `enabled` to `false`:

```json
{
  "id": "PY003",
  ...
  "enabled": false,
  "comment": "Team uses print() for scripting — disabled."
}
```

---

### Checklist before adding a rule

- [ ] `id` is unique across all rule files
- [ ] `severity` is appropriate (`error` only for things that should always block)
- [ ] `pattern` tested against real examples — check for false positives
- [ ] `file_extensions` is set correctly (don't run JS rules on Python files)
- [ ] `exclude_file_patterns` excludes test files if the rule would produce noise there
- [ ] `fix_suggestion` gives a concrete, actionable fix
- [ ] `fallback_pattern` provided for any `ast` type rule
- [ ] `enabled: false` if the rule is too noisy for most teams

---

*Rules Reference — Code Review Agent v1.0 — B4G Projects*




Please perform a comprehensive, production-grade code review of the provided codebase.

Evaluate the code from an industry-standard (scalable SaaS / enterprise-level) perspective, covering both frontend and backend where applicable.

---

### 1. Code Quality & Standards

* Clean code principles (readability, simplicity, maintainability)
* Consistency across the codebase
* Proper formatting and structure

### 2. Architecture & Design

* Separation of concerns (Controller / Service / Repository layers)
* Modularity and scalability
* Coupling vs cohesion
* Use of design patterns (if applicable)
* Readiness for scaling (monolith vs modular structure)

### 3. Folder Structure & Organization

* Logical and maintainable folder structure
* Feature-based vs layer-based organization
* File size and single responsibility principle

### 4. Naming Conventions

* Variables, functions, classes, files
* Consistency and clarity
* Meaningful and self-explanatory names

### 5. Type Safety

* Type casting issues
* Proper type hinting / typings (TypeScript, Python, etc.)

### 6. Code Duplication & Consistency

* DRY violations
* Repeated logic patterns
* Inconsistent implementations

### 7. Performance & Optimization

* Time complexity issues
* Unnecessary loops or computations
* API response optimization
* Database query efficiency (N+1 issues)
* Caching opportunities

### 8. Database & Query Review

* Query optimization
* Index usage
* ORM misuse
* Transaction handling
* Schema design issues

### 9. API Design (Backend)

* RESTful standards
* Endpoint naming consistency
* Versioning strategy
* Request/response structure
* Pagination, filtering, sorting

### 10. Frontend Best Practices

* Component reusability and structure
* State management (Redux, Context, etc.)
* Performance (re-renders, memoization)
* Lazy loading / code splitting
* Accessibility (a11y basics)

### 11. Security Review

* Input validation & sanitization
* Authentication & authorization flaws
* SQL Injection, XSS, CSRF risks
* Secrets management (env variables, vaults)
* File upload validation
* API security best practices

### 12. Error Handling & Logging

* Centralized error handling
* Proper HTTP status codes
* Meaningful error messages
* Logging strategy (info/debug/error)
* No sensitive data exposure in logs

### 13. Testing

* Test structure (unit, integration, e2e)
* Naming conventions
* Coverage and edge cases
* Mocking strategy
* Test readability and maintainability

### 14. Dependency Management

* Unused dependencies
* Outdated or vulnerable packages
* Version management

### 15. Configuration Management

* Environment-based configurations
* No hardcoded secrets or values

### 16. Code Smells & Red Flags

* Large files (God classes)
* Deep nesting
* Magic numbers
* Dead or unused code

### 17. Scalability & Production Readiness

* Stateless design
* Horizontal scalability readiness
* Background jobs / queue handling
* Load handling considerations

---

## 🔍 Output Requirements

1. Categorize issues by severity:

   * High (Critical / Security / Breaking)
   * Medium (Performance / Maintainability)
   * Low (Style / Minor Improvements)

2. For each issue:

   * Explain the problem clearly
   * Provide suggested fix or improvement

3. Highlight:

   * Quick wins (easy improvements)
   * Major risks in production

4. Provide:

   * A prioritized refactoring roadmap (step-by-step)
   * Overall code quality score (out of 10)

---

Focus on practical, real-world improvements aligned with modern engineering standards.
 


 Please perform a comprehensive, production-grade code review of the provided codebase.

Evaluate the code from an industry-standard (scalable SaaS / enterprise-level) perspective, covering both frontend and backend where applicable.

---

### 1. Code Quality & Standards

* Clean code principles (readability, simplicity, maintainability)
* Consistency across the codebase
* Proper formatting and structure

### 2. Architecture & Design

* Separation of concerns (Controller / Service / Repository layers)
* Modularity and scalability
* Coupling vs cohesion
* Use of design patterns (if applicable)
* Readiness for scaling (monolith vs modular structure)

### 3. Folder Structure & Organization

* Logical and maintainable folder structure
* Feature-based vs layer-based organization
* File size and single responsibility principle

### 4. Naming Conventions

* Variables, functions, classes, files
* Consistency and clarity
* Meaningful and self-explanatory names

### 5. Type Safety

* Type casting issues
* Proper type hinting / typings (TypeScript, Python, etc.)

### 6. Code Duplication & Consistency

* DRY violations
* Repeated logic patterns
* Inconsistent implementations

### 7. Performance & Optimization

* Time complexity issues
* Unnecessary loops or computations
* API response optimization
* Database query efficiency (N+1 issues)
* Caching opportunities

### 8. Database & Query Review

* Query optimization
* Index usage
* ORM misuse
* Transaction handling
* Schema design issues

### 9. API Design (Backend)

* RESTful standards
* Endpoint naming consistency
* Versioning strategy
* Request/response structure
* Pagination, filtering, sorting

### 10. Frontend Best Practices

* Component reusability and structure
* State management (Redux, Context, etc.)
* Performance (re-renders, memoization)
* Lazy loading / code splitting
* Accessibility (a11y basics)

### 11. Security Review

* Input validation & sanitization
* Authentication & authorization flaws
* SQL Injection, XSS, CSRF risks
* Secrets management (env variables, vaults)
* File upload validation
* API security best practices

### 12. Error Handling & Logging

* Centralized error handling
* Proper HTTP status codes
* Meaningful error messages
* Logging strategy (info/debug/error)
* No sensitive data exposure in logs

### 13. Testing

* Test structure (unit, integration, e2e)
* Naming conventions
* Coverage and edge cases
* Mocking strategy
* Test readability and maintainability

### 14. Dependency Management

* Unused dependencies
* Outdated or vulnerable packages
* Version management

### 15. Configuration Management

* Environment-based configurations
* No hardcoded secrets or values

### 16. Code Smells & Red Flags

* Large files (God classes)
* Deep nesting
* Magic numbers
* Dead or unused code

### 17. Scalability & Production Readiness

* Stateless design
* Horizontal scalability readiness
* Background jobs / queue handling
* Load handling considerations

---

### 18. Git & Security (Version Control Best Practices)

* Verify `.gitignore` is properly configured:

  * Ensure sensitive files are NOT tracked (e.g., `.env`, `.env.*`, secrets, private keys, credentials)
  * Ensure unnecessary files are excluded (e.g., `node_modules/`, `vendor/`, build folders, logs, cache files)
  * Ensure required files are NOT mistakenly ignored

* Identify IMPORTANT files that SHOULD be in the repository but are missing due to misconfigured `.gitignore`:

  * `.env.example` or sample configuration files
  * Required config files (non-sensitive)
  * Migration files / schema definitions
  * Lock files (`package-lock.json`, `yarn.lock`, `poetry.lock`, etc.)
  * Docker files (`Dockerfile`, `docker-compose.yml`)
  * CI/CD configs (if present)
  * Essential scripts

* Check for sensitive data exposure:

  * Hardcoded API keys, tokens, passwords
  * Secrets in config files or source code
  * Private keys or certificates in repository

* Validate what SHOULD be pushed to Git:

  * Source code
  * Configuration templates (e.g., `.env.example`)
  * Documentation (README, setup guide)
  * Database migrations and schema files
  * Dependency lock files

* Validate what SHOULD NOT be pushed:

  * Environment files (`.env`)
  * Build artifacts (`dist/`, `build/`)
  * Dependency folders (`node_modules/`, `vendor/`)
  * Logs and temporary files
  * OS-specific files (`.DS_Store`, `Thumbs.db`)

* Check for secure practices:

  * Use of environment variables for secrets
  * Proper secrets management (Vault, AWS Secrets Manager, etc.)
  * No credentials in commit history (if possible, flag risk)

* Check Git history:

  * Secrets or credentials in previous commits
  * Suggest removal using tools like git filter-repo or BFG

* Check for large files:

  * Identify large files accidentally committed
  * Suggest using Git LFS if needed

* Review commit practices:

  * Meaningful commit messages
  * Proper branching strategy (feature/bugfix/hotfix)
  * Avoid direct commits to main/master branch

* Identify risks:

  * Previously committed sensitive data
  * Misconfigured `.gitignore`
  * Missing critical files affecting project setup
  * Large or unnecessary files in repo

* Provide fixes:

  * Suggest corrections in `.gitignore`
  * Suggest files to be added/removed from repository
  * Suggest recovery steps if important files are missing

---

## 🔍 Output Requirements

1. Categorize issues by severity:

   * High (Critical / Security / Breaking)
   * Medium (Performance / Maintainability)
   * Low (Style / Minor Improvements)

2. For each issue:

   * Explain the problem clearly
   * Provide suggested fix or improvement

3. Explicitly list:

   * Files that should be removed from the repository
   * Files that should be added but are currently missing
   * Corrections required in the `.gitignore` file

4. Highlight:

   * Quick wins (easy improvements)
   * Major risks in production

5. Provide:

   * A prioritized refactoring roadmap (step-by-step)
   * Overall code quality score (out of 10)

---

Focus on practical, real-world improvements aligned with modern engineering standards.


     