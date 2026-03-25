"""Generic regex-only analyzer for files without a dedicated language analyzer."""

from typing import Any, Dict, List

from agent.analyzer.base_analyzer import BaseAnalyzer
from agent.utils.reporter import Violation


class GenericAnalyzer(BaseAnalyzer):
    """Fallback analyzer that always returns no AST violations.

    The RuleEngine already handles regex rules for all file types.
    This class exists so the engine has a valid analyzer object for
    languages that don't have dedicated AST support yet.
    """

    def run_ast_check(
        self,
        file_path: str,
        content: str,
        rule: Dict[str, Any],
        ast_check: str,
    ) -> List[Violation]:
        # No AST checks for generic files — regex rules still apply via the engine
        return []
