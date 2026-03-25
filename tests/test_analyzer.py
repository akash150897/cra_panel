"""Tests for Python AST analyzer and JavaScript heuristic analyzer."""

import unittest

from agent.analyzer.javascript_analyzer import JavaScriptAnalyzer
from agent.analyzer.python_analyzer import PythonAnalyzer
from agent.utils.reporter import Severity


def _rule(rule_id: str, ast_check: str, severity: str = "error") -> dict:
    return {
        "id": rule_id,
        "name": rule_id.lower(),
        "severity": severity,
        "message": "Test violation",
        "fix_suggestion": "",
        "category": "test",
        "ast_check": ast_check,
    }


class TestPythonAnalyzer(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = PythonAnalyzer()

    def _check(self, code: str, ast_check: str, severity: str = "error"):
        rule = _rule("TEST", ast_check, severity)
        return self.analyzer.run_ast_check("test.py", code, rule, ast_check)

    # -- bare except -------------------------------------------------------

    def test_bare_except_detected(self) -> None:
        code = "try:\n    pass\nexcept:\n    pass\n"
        violations = self._check(code, "bare_except")
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].severity, Severity.ERROR)

    def test_specific_except_not_flagged(self) -> None:
        code = "try:\n    pass\nexcept ValueError:\n    pass\n"
        violations = self._check(code, "bare_except")
        self.assertEqual(len(violations), 0)

    # -- wildcard imports --------------------------------------------------

    def test_wildcard_import_detected(self) -> None:
        code = "from os.path import *\n"
        violations = self._check(code, "wildcard_import")
        self.assertEqual(len(violations), 1)

    def test_normal_import_not_flagged(self) -> None:
        code = "from os.path import join, exists\n"
        violations = self._check(code, "wildcard_import")
        self.assertEqual(len(violations), 0)

    # -- print usage -------------------------------------------------------

    def test_print_detected(self) -> None:
        code = "print('hello')\n"
        violations = self._check(code, "print_usage", "warning")
        self.assertEqual(len(violations), 1)

    def test_logging_not_flagged(self) -> None:
        code = "import logging\nlogging.info('hello')\n"
        violations = self._check(code, "print_usage", "warning")
        self.assertEqual(len(violations), 0)

    # -- eval / exec -------------------------------------------------------

    def test_eval_detected(self) -> None:
        code = "result = eval(user_input)\n"
        violations = self._check(code, "eval_exec_usage")
        self.assertEqual(len(violations), 1)

    def test_exec_detected(self) -> None:
        code = "exec('import os')\n"
        violations = self._check(code, "eval_exec_usage")
        self.assertEqual(len(violations), 1)

    # -- type hints --------------------------------------------------------

    def test_missing_type_hints_detected(self) -> None:
        code = "def greet(name):\n    return 'hi'\n"
        violations = self._check(code, "missing_type_hints", "warning")
        self.assertTrue(len(violations) >= 1)

    def test_fully_typed_function_not_flagged(self) -> None:
        code = "def greet(name: str) -> str:\n    return 'hi'\n"
        violations = self._check(code, "missing_type_hints", "warning")
        self.assertEqual(len(violations), 0)

    # -- snake_case --------------------------------------------------------

    def test_camelcase_function_detected(self) -> None:
        code = "def getUserName():\n    pass\n"
        violations = self._check(code, "snake_case_functions", "warning")
        self.assertEqual(len(violations), 1)

    def test_snake_case_function_not_flagged(self) -> None:
        code = "def get_user_name():\n    pass\n"
        violations = self._check(code, "snake_case_functions", "warning")
        self.assertEqual(len(violations), 0)

    # -- unused imports ----------------------------------------------------

    def test_unused_import_detected(self) -> None:
        code = "import os\n\ndef foo() -> None:\n    pass\n"
        violations = self._check(code, "no_unused_imports", "warning")
        self.assertEqual(len(violations), 1)

    def test_used_import_not_flagged(self) -> None:
        code = "import os\n\ndef foo() -> str:\n    return os.getcwd()\n"
        violations = self._check(code, "no_unused_imports", "warning")
        self.assertEqual(len(violations), 0)

    # -- syntax error handled gracefully -----------------------------------

    def test_syntax_error_returns_empty(self) -> None:
        code = "def broken(:\n    pass\n"
        violations = self._check(code, "bare_except")
        self.assertEqual(violations, [])


class TestJavaScriptAnalyzer(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = JavaScriptAnalyzer()

    def _check(self, code: str, ast_check: str, severity: str = "warning"):
        rule = _rule("JSTEST", ast_check, severity)
        return self.analyzer.run_ast_check("test.tsx", code, rule, ast_check)

    def test_class_component_detected(self) -> None:
        code = "class MyComp extends React.Component {\n  render() { return null; }\n}\n"
        violations = self._check(code, "no_class_components")
        self.assertEqual(len(violations), 1)

    def test_functional_component_not_flagged(self) -> None:
        code = "const MyComp = () => null;\n"
        violations = self._check(code, "no_class_components")
        self.assertEqual(len(violations), 0)

    def test_console_log_detected(self) -> None:
        code = "function foo() { console.log('debug'); }\n"
        violations = self._check(code, "no_console_log")
        self.assertEqual(len(violations), 1)

    def test_console_in_comment_not_flagged(self) -> None:
        code = "// console.log('debug');\n"
        violations = self._check(code, "no_console_log")
        self.assertEqual(len(violations), 0)

    def test_var_detected(self) -> None:
        code = "var x = 1;\n"
        violations = self._check(code, "no_var_declaration")
        self.assertEqual(len(violations), 1)

    def test_jwt_in_localstorage_detected(self) -> None:
        code = "localStorage.setItem('token', jwt);\n"
        violations = self._check(code, "no_jwt_in_localstorage", "error")
        self.assertEqual(len(violations), 1)

    def test_asyncstorage_secret_detected(self) -> None:
        code = "AsyncStorage.setItem('token', value);\n"
        violations = self._check(code, "no_async_storage_secrets", "error")
        self.assertEqual(len(violations), 1)

    def test_any_type_detected(self) -> None:
        code = "const x: any = {};\n"
        violations = self._check(code, "no_any_type")
        self.assertEqual(len(violations), 1)

    def test_raw_anchor_detected(self) -> None:
        code = '<a href="/home">Home</a>\n'
        violations = self._check(code, "no_raw_anchor")
        self.assertEqual(len(violations), 1)

    def test_external_anchor_not_flagged(self) -> None:
        code = '<a href="https://example.com">External</a>\n'
        violations = self._check(code, "no_raw_anchor")
        self.assertEqual(len(violations), 0)


if __name__ == "__main__":
    unittest.main()
