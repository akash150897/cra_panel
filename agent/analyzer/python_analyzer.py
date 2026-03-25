"""AST-based analyzer for Python source files.

Uses the built-in ``ast`` module to perform deep structural checks that
simple regex patterns cannot reliably handle.
"""

import ast
import re
from typing import Any, Dict, List, Optional, Set

from agent.analyzer.base_analyzer import BaseAnalyzer
from agent.utils.logger import get_logger
from agent.utils.reporter import Severity, Violation

logger = get_logger(__name__)

_SNAKE_CASE_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def _make_violation(
    rule: Dict[str, Any],
    file_path: str,
    line_no: int,
    message_override: Optional[str] = None,
    snippet: str = "",
) -> Violation:
    return Violation(
        rule_id=rule["id"],
        rule_name=rule.get("name", ""),
        severity=Severity(rule.get("severity", "warning")),
        file_path=file_path,
        line_number=line_no,
        message=message_override or rule.get("message", ""),
        fix_suggestion=rule.get("fix_suggestion", ""),
        snippet=snippet,
        category=rule.get("category", ""),
    )


class PythonAnalyzer(BaseAnalyzer):
    """Deep Python static analysis using the standard ast module."""

    # Dispatch table: ast_check id → method name
    _CHECK_DISPATCH = {
        "bare_except": "_check_bare_except",
        "wildcard_import": "_check_wildcard_imports",
        "print_usage": "_check_print_usage",
        "eval_exec_usage": "_check_eval_exec",
        "missing_type_hints": "_check_missing_type_hints",
        "snake_case_functions": "_check_snake_case_functions",
        "no_unused_imports": "_check_unused_imports",
    }

    def run_ast_check(
        self,
        file_path: str,
        content: str,
        rule: Dict[str, Any],
        ast_check: str,
    ) -> List[Violation]:
        """Dispatch to the appropriate AST check method."""
        method_name = self._CHECK_DISPATCH.get(ast_check)
        if not method_name:
            logger.debug("Unknown AST check '%s' for Python", ast_check)
            return []

        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError as exc:
            logger.warning("Syntax error parsing %s: %s", file_path, exc)
            return []

        method = getattr(self, method_name)
        lines = content.splitlines()
        return method(tree, file_path, content, lines, rule)

    # ------------------------------------------------------------------
    # AST check implementations
    # ------------------------------------------------------------------

    def _check_bare_except(
        self,
        tree: ast.AST,
        file_path: str,
        content: str,
        lines: List[str],
        rule: Dict[str, Any],
    ) -> List[Violation]:
        """Detect bare ``except:`` clauses (PEP 8 / error handling guideline)."""
        violations: List[Violation] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                line_no = node.lineno
                snippet = lines[line_no - 1] if line_no <= len(lines) else ""
                violations.append(
                    _make_violation(
                        rule, file_path, line_no,
                        message_override="Bare 'except:' catches all exceptions including system exits. "
                                         "Use 'except Exception as e:' or a specific exception type.",
                        snippet=snippet,
                    )
                )
        return violations

    def _check_wildcard_imports(
        self,
        tree: ast.AST,
        file_path: str,
        content: str,
        lines: List[str],
        rule: Dict[str, Any],
    ) -> List[Violation]:
        """Detect ``from module import *`` statements."""
        violations: List[Violation] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        line_no = node.lineno
                        snippet = lines[line_no - 1] if line_no <= len(lines) else ""
                        violations.append(
                            _make_violation(
                                rule, file_path, line_no,
                                message_override=f"Wildcard import from '{node.module}' pollutes the namespace. "
                                                 "Import only what you need.",
                                snippet=snippet,
                            )
                        )
        return violations

    def _check_print_usage(
        self,
        tree: ast.AST,
        file_path: str,
        content: str,
        lines: List[str],
        rule: Dict[str, Any],
    ) -> List[Violation]:
        """Detect direct ``print()`` calls — use ``logging`` instead."""
        violations: List[Violation] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                is_print = (
                    (isinstance(func, ast.Name) and func.id == "print")
                    or (isinstance(func, ast.Attribute) and func.attr == "print")
                )
                if is_print:
                    line_no = node.lineno
                    snippet = lines[line_no - 1] if line_no <= len(lines) else ""
                    violations.append(
                        _make_violation(
                            rule, file_path, line_no,
                            message_override="Use 'logging' instead of print() for backend/library code.",
                            snippet=snippet,
                        )
                    )
        return violations

    def _check_eval_exec(
        self,
        tree: ast.AST,
        file_path: str,
        content: str,
        lines: List[str],
        rule: Dict[str, Any],
    ) -> List[Violation]:
        """Detect usage of ``eval()`` or ``exec()`` — security risk."""
        violations: List[Violation] = []
        dangerous = {"eval", "exec"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = None
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name in dangerous:
                    line_no = node.lineno
                    snippet = lines[line_no - 1] if line_no <= len(lines) else ""
                    violations.append(
                        _make_violation(
                            rule, file_path, line_no,
                            message_override=f"'{name}()' is a security risk. "
                                             "Never use eval/exec with untrusted input.",
                            snippet=snippet,
                        )
                    )
        return violations

    def _check_missing_type_hints(
        self,
        tree: ast.AST,
        file_path: str,
        content: str,
        lines: List[str],
        rule: Dict[str, Any],
    ) -> List[Violation]:
        """Flag public functions/methods that are missing type annotations."""
        violations: List[Violation] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # Skip private/dunder methods
            if node.name.startswith("_"):
                continue

            args = node.args
            all_params = args.args + args.posonlyargs + args.kwonlyargs
            if args.vararg:
                all_params.append(args.vararg)
            if args.kwarg:
                all_params.append(args.kwarg)

            unannotated = [
                a.arg for a in all_params
                if a.annotation is None and a.arg != "self" and a.arg != "cls"
            ]
            missing_return = node.returns is None

            if unannotated or missing_return:
                line_no = node.lineno
                snippet = lines[line_no - 1] if line_no <= len(lines) else ""
                missing_parts: List[str] = []
                if unannotated:
                    missing_parts.append(f"params: {', '.join(unannotated)}")
                if missing_return:
                    missing_parts.append("return type")
                violations.append(
                    _make_violation(
                        rule, file_path, line_no,
                        message_override=f"Function '{node.name}' is missing type hints for {'; '.join(missing_parts)}.",
                        snippet=snippet,
                    )
                )
        return violations

    def _check_snake_case_functions(
        self,
        tree: ast.AST,
        file_path: str,
        content: str,
        lines: List[str],
        rule: Dict[str, Any],
    ) -> List[Violation]:
        """Flag functions whose names are not snake_case (PEP 8)."""
        violations: List[Violation] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = node.name
            if name.startswith("__") and name.endswith("__"):
                continue  # dunder methods are exempt
            if not _SNAKE_CASE_RE.match(name):
                line_no = node.lineno
                snippet = lines[line_no - 1] if line_no <= len(lines) else ""
                violations.append(
                    _make_violation(
                        rule, file_path, line_no,
                        message_override=f"Function '{name}' should use snake_case naming (PEP 8).",
                        snippet=snippet,
                    )
                )
        return violations

    def _check_unused_imports(
        self,
        tree: ast.AST,
        file_path: str,
        content: str,
        lines: List[str],
        rule: Dict[str, Any],
    ) -> List[Violation]:
        """Detect imports that are never referenced in the module body."""
        violations: List[Violation] = []

        # Collect all imported names
        imported: Dict[str, int] = {}  # name → line number
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local_name = alias.asname or alias.name.split(".")[0]
                    imported[local_name] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    local_name = alias.asname or alias.name
                    imported[local_name] = node.lineno

        # Collect all Name usages outside import statements
        used: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                # e.g. os.path — the root 'os' counts as used
                if isinstance(node.value, ast.Name):
                    used.add(node.value.id)

        for name, line_no in imported.items():
            if name not in used:
                snippet = lines[line_no - 1] if line_no <= len(lines) else ""
                violations.append(
                    _make_violation(
                        rule, file_path, line_no,
                        message_override=f"Import '{name}' is never used. Remove it to keep the code clean.",
                        snippet=snippet,
                    )
                )
        return violations
