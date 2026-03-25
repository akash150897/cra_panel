"""Tests for language and framework detection."""

import os
import tempfile
import unittest
from pathlib import Path

from agent.detector.framework_detector import FrameworkDetector
from agent.detector.language_detector import LanguageDetector
from agent.detector.project_context import build_project_context


class TestLanguageDetector(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()

    def _write(self, name: str, content: str = "") -> None:
        (Path(self.tmpdir) / name).write_text(content, encoding="utf-8")

    def test_detects_python_via_requirements(self) -> None:
        self._write("requirements.txt", "fastapi\npydantic\n")
        detector = LanguageDetector(self.tmpdir)
        self.assertEqual(detector.detect_primary_language(), "python")

    def test_detects_javascript_via_package_json(self) -> None:
        self._write("package.json", '{"dependencies": {"react": "^18.0.0"}}')
        detector = LanguageDetector(self.tmpdir)
        self.assertEqual(detector.detect_primary_language(), "javascript")

    def test_detects_typescript_via_package_json(self) -> None:
        self._write(
            "package.json",
            '{"dependencies": {"react": "^18"}, "devDependencies": {"typescript": "^5"}}',
        )
        detector = LanguageDetector(self.tmpdir)
        self.assertEqual(detector.detect_primary_language(), "typescript")

    def test_file_language_by_extension(self) -> None:
        detector = LanguageDetector(self.tmpdir)
        self.assertEqual(detector.detect_file_language("app.py"), "python")
        self.assertEqual(detector.detect_file_language("index.tsx"), "typescript")
        self.assertEqual(detector.detect_file_language("main.go"), "go")
        self.assertIsNone(detector.detect_file_language("README.md"))

    def test_unknown_project(self) -> None:
        detector = LanguageDetector(self.tmpdir)
        self.assertEqual(detector.detect_primary_language(), "unknown")


class TestFrameworkDetector(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()

    def _write(self, name: str, content: str = "") -> None:
        path = Path(self.tmpdir) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_detects_react_via_package_json(self) -> None:
        self._write("package.json", '{"dependencies": {"react": "^18"}}')
        detector = FrameworkDetector(self.tmpdir)
        self.assertEqual(detector.detect(), "react")

    def test_detects_nextjs_before_react(self) -> None:
        self._write(
            "package.json",
            '{"dependencies": {"next": "14", "react": "^18"}}',
        )
        detector = FrameworkDetector(self.tmpdir)
        self.assertEqual(detector.detect(), "nextjs")

    def test_detects_react_native_before_react(self) -> None:
        self._write(
            "package.json",
            '{"dependencies": {"react-native": "0.73", "react": "^18"}}',
        )
        detector = FrameworkDetector(self.tmpdir)
        self.assertEqual(detector.detect(), "react_native")

    def test_detects_fastapi_via_requirements(self) -> None:
        self._write("requirements.txt", "fastapi\nuvicorn\n")
        detector = FrameworkDetector(self.tmpdir)
        self.assertEqual(detector.detect(), "fastapi")

    def test_detects_django_via_manage_py(self) -> None:
        self._write("manage.py", "# Django manage.py")
        detector = FrameworkDetector(self.tmpdir)
        self.assertEqual(detector.detect(), "django")

    def test_detects_express_via_package_json(self) -> None:
        self._write("package.json", '{"dependencies": {"express": "^4"}}')
        detector = FrameworkDetector(self.tmpdir)
        self.assertEqual(detector.detect(), "express")

    def test_no_framework_returns_none(self) -> None:
        detector = FrameworkDetector(self.tmpdir)
        self.assertIsNone(detector.detect())


class TestBuildProjectContext(unittest.TestCase):
    def test_overrides_respected(self) -> None:
        ctx = build_project_context(
            project_root=".",
            files_to_review=["app.py"],
            language_override="python",
            framework_override="fastapi",
        )
        self.assertEqual(ctx.language, "python")
        self.assertEqual(ctx.framework, "fastapi")
        self.assertEqual(ctx.files_to_review, ["app.py"])


if __name__ == "__main__":
    unittest.main()
