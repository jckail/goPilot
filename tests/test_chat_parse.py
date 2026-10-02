"""Offline output-path regressions for the actual thread-link parser."""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "chat_parse", Path(__file__).resolve().parents[1] / "goHelpers" / "chatParse.py"
)
chat_parse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chat_parse)


class ThreadOutputTests(unittest.TestCase):
    payload = (
        "irrelevant diagnostic\n"
        "View response here: https://example.invalid/thread/one\n"
        "View response here: https://example.invalid/thread/one\n"
        "View response here: https://example.invalid/thread/two\n"
    )
    expected = {
        "View response here: https://example.invalid/thread/one",
        "View response here: https://example.invalid/thread/two",
    }

    def assert_output(self, source, argument=None):
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(self.payload, encoding="utf-8")
        original = source.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            chat_parse.parse_and_save_unique_threads(str(argument or source))
        output = source.with_name("unique_" + source.name)
        lines = output.read_text(encoding="utf-8").splitlines()
        self.assertEqual(set(lines), self.expected)
        self.assertEqual(len(lines), len(self.expected))
        self.assertEqual(set(stdout.getvalue().splitlines()), self.expected)
        self.assertEqual(source.read_bytes(), original)

    def test_ordinary_absolute_path(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assert_output(Path(directory) / "logs" / "report.txt")

    def test_relative_path_keeps_parent_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            original_cwd = os.getcwd()
            try:
                os.chdir(directory)
                self.assert_output(Path(directory) / "logs" / "report.txt", "logs/report.txt")
            finally:
                os.chdir(original_cwd)

    def test_matching_basename_in_parent_does_not_require_redirect_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assert_output(root / "report.txt" / "archive" / "report.txt")
            self.assertFalse((root / "unique_report.txt").exists())

    def test_existing_redirected_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unrelated = root / "unique_report.txt" / "archive" / "unique_report.txt"
            unrelated.parent.mkdir(parents=True)
            sentinel = b"unrelated previously generated output\n"
            unrelated.write_bytes(sentinel)
            try:
                self.assert_output(root / "report.txt" / "archive" / "report.txt")
            finally:
                self.assertEqual(unrelated.read_bytes(), sentinel)

    def test_parent_substring_and_spaces_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "team report.txt archive" / "nested space" / "report.txt"
            self.assert_output(source)
            self.assertFalse((root / "team unique_report.txt archive").exists())


if __name__ == "__main__":
    unittest.main()
