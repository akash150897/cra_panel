"""Abstract base class for language-specific AST analyzers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from agent.utils.reporter import Violation


class BaseAnalyzer(ABC):
    """Contract for AST-based analyzers.

    Each language-specific subclass implements ``run_ast_check`` which
    maps ``ast_check`` identifiers (set in rule JSON) to concrete AST
    inspection routines.
    """

    @abstractmethod
    def run_ast_check(
        self,
        file_path: str,
        content: str,
        rule: Dict[str, Any],
        ast_check: str,
    ) -> List[Violation]:
        """Execute a named AST check against the given source file.

        Args:
            file_path: Path shown in violation reports.
            content: Full text content of the file.
            rule: The rule dictionary (for severity, message, etc.).
            ast_check: Identifier for the specific check to perform.

        Returns:
            List of Violation objects (empty if no issues found).
        """
