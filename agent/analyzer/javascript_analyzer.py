"""Heuristic analyzer for JavaScript and TypeScript files.

Tree-sitter would provide true AST parsing but requires a compiled
native extension. This analyzer uses carefully constructed regex
patterns combined with structural heuristics to approximate many of
the same checks, keeping the agent dependency-free.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from agent.analyzer.base_analyzer import BaseAnalyzer
from agent.utils.logger import get_logger
from agent.utils.reporter import Severity, Violation

logger = get_logger(__name__)


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


def _find_pattern_lines(
    pattern: str, content: str, flags: int = 0
) -> List[Tuple[int, str]]:
    """Return (line_no, line_text) for each line matching the pattern."""
    try:
        compiled = re.compile(pattern, flags)
    except re.error:
        return []
    results: List[Tuple[int, str]] = []
    for i, line in enumerate(content.splitlines(), start=1):
        if compiled.search(line):
            results.append((i, line))
    return results


class JavaScriptAnalyzer(BaseAnalyzer):
    """Heuristic/regex-based analyzer for JS and TS source files."""

    _CHECK_DISPATCH = {
        "no_class_components": "_check_class_components",
        "no_console_log": "_check_console_log",
        "no_var_declaration": "_check_var_declaration",
        "no_inline_styles": "_check_inline_styles",
        "no_async_storage_secrets": "_check_async_storage_secrets",
        "no_jwt_in_localstorage": "_check_jwt_in_localstorage",
        "no_any_type": "_check_any_type",
        "use_flatlist": "_check_use_flatlist",
        "no_raw_anchor": "_check_raw_anchor",
    }

    def run_ast_check(
        self,
        file_path: str,
        content: str,
        rule: Dict[str, Any],
        ast_check: str,
    ) -> List[Violation]:
        method_name = self._CHECK_DISPATCH.get(ast_check)
        if not method_name:
            logger.debug("Unknown JS check '%s'", ast_check)
            return []
        method = getattr(self, method_name)
        return method(file_path, content, rule)

    # ------------------------------------------------------------------
    # Check implementations
    # ------------------------------------------------------------------

    def _check_class_components(
        self, file_path: str, content: str, rule: Dict[str, Any]
    ) -> List[Violation]:
        """Detect React class components — use functional components instead."""
        pattern = r"class\s+\w+\s+extends\s+(React\.Component|Component|PureComponent)"
        violations = []
        for line_no, snippet in _find_pattern_lines(pattern, content):
            violations.append(
                _make_violation(
                    rule, file_path, line_no,
                    message_override="Class component detected. Use functional components with hooks instead.",
                    snippet=snippet,
                )
            )
        return violations

    def _check_console_log(
        self, file_path: str, content: str, rule: Dict[str, Any]
    ) -> List[Violation]:
        """Detect console.log/warn/error calls."""
        # Skip lines that are comments
        pattern = r"(?<!//\s)console\.(log|warn|error|debug|info)\s*\("
        violations = []
        for i, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            if re.search(pattern, line):
                violations.append(
                    _make_violation(
                        rule, file_path, i,
                        message_override="Remove console statements before pushing. Use a logger instead.",
                        snippet=line,
                    )
                )
        return violations

    def _check_var_declaration(
        self, file_path: str, content: str, rule: Dict[str, Any]
    ) -> List[Violation]:
        """Flag 'var' declarations — use const/let."""
        pattern = r"\bvar\s+\w+"
        violations = []
        for line_no, snippet in _find_pattern_lines(pattern, content):
            stripped = snippet.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            violations.append(
                _make_violation(
                    rule, file_path, line_no,
                    message_override="'var' is function-scoped and error-prone. Use 'const' or 'let' instead.",
                    snippet=snippet,
                )
            )
        return violations

    def _check_inline_styles(
        self, file_path: str, content: str, rule: Dict[str, Any]
    ) -> List[Violation]:
        """Detect inline style objects in JSX / React Native."""
        # Match style={{ ... }} or style={styles.inline_object}
        pattern = r'style=\{\s*\{'
        violations = []
        for line_no, snippet in _find_pattern_lines(pattern, content):
            violations.append(
                _make_violation(
                    rule, file_path, line_no,
                    message_override="Avoid inline style objects. Use StyleSheet.create() or CSS Modules.",
                    snippet=snippet,
                )
            )
        return violations

    def _check_async_storage_secrets(
        self, file_path: str, content: str, rule: Dict[str, Any]
    ) -> List[Violation]:
        """Detect AsyncStorage usage for tokens/secrets (React Native)."""
        # Sensitive keys commonly stored in AsyncStorage
        pattern = (
            r"AsyncStorage\.(setItem|getItem)\s*\(\s*['\"]"
            r"(token|jwt|auth|password|secret|credential|key|api_key)"
        )
        violations = []
        for line_no, snippet in _find_pattern_lines(pattern, content, re.IGNORECASE):
            violations.append(
                _make_violation(
                    rule, file_path, line_no,
                    message_override="Do not store secrets/tokens in AsyncStorage (insecure). "
                                     "Use react-native-keychain or expo-secure-store.",
                    snippet=snippet,
                )
            )
        return violations

    def _check_jwt_in_localstorage(
        self, file_path: str, content: str, rule: Dict[str, Any]
    ) -> List[Violation]:
        """Detect JWT/token storage in localStorage or sessionStorage."""
        pattern = (
            r"(localStorage|sessionStorage)\.(setItem|getItem)\s*\(\s*['\"]"
            r"(token|jwt|auth|access_token|refresh_token)"
        )
        violations = []
        for line_no, snippet in _find_pattern_lines(pattern, content, re.IGNORECASE):
            violations.append(
                _make_violation(
                    rule, file_path, line_no,
                    message_override="Never store JWTs in localStorage/sessionStorage (XSS risk). "
                                     "Use HttpOnly cookies instead.",
                    snippet=snippet,
                )
            )
        return violations

    def _check_any_type(
        self, file_path: str, content: str, rule: Dict[str, Any]
    ) -> List[Violation]:
        """Flag explicit 'any' type annotations in TypeScript."""
        pattern = r":\s*any\b"
        violations = []
        for i, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            if re.search(pattern, line):
                violations.append(
                    _make_violation(
                        rule, file_path, i,
                        message_override="Avoid 'any' type — provide an explicit type or use 'unknown' with a type guard.",
                        snippet=line,
                    )
                )
        return violations

    def _check_use_flatlist(
        self, file_path: str, content: str, rule: Dict[str, Any]
    ) -> List[Violation]:
        """Warn when .map() is used to render long lists instead of FlatList."""
        # Heuristic: .map( inside JSX return with no FlatList in the same file
        if "FlatList" in content or "SectionList" in content or "VirtualizedList" in content:
            return []  # Already using the correct component
        pattern = r"\{\s*\w+\.(map)\s*\("
        violations = []
        for line_no, snippet in _find_pattern_lines(pattern, content):
            violations.append(
                _make_violation(
                    rule, file_path, line_no,
                    message_override="Use FlatList/SectionList instead of .map() for large or dynamic lists "
                                     "to enable virtualization and better performance.",
                    snippet=snippet,
                )
            )
        return violations

    def _check_raw_anchor(
        self, file_path: str, content: str, rule: Dict[str, Any]
    ) -> List[Violation]:
        """Detect raw <a href> used for internal navigation (use Link instead)."""
        # Flag <a href="/..."> or <a href="..." that are internal paths
        pattern = r'<a\s[^>]*href=["\']/'
        violations = []
        for line_no, snippet in _find_pattern_lines(pattern, content):
            violations.append(
                _make_violation(
                    rule, file_path, line_no,
                    message_override="Use <Link> (React Router / Next.js) instead of raw <a> for internal navigation.",
                    snippet=snippet,
                )
            )
        return violations
