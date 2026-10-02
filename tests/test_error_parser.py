"""Execute the actual error-parser entry with an inert provider adapter."""

import contextlib
import io
import os
from pathlib import Path
import runpy
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "goHelpers" / "errorParser.py"


class ErrorParserEntryTests(unittest.TestCase):
    def execute(self, arguments):
        calls = []
        self.last_calls = calls
        class Manager:
            def __init__(self, name, helper):
                calls.append(("manager", name, helper))
            def createThread(self, errors):
                calls.append(("thread", errors))
        adapter = types.ModuleType("addGo")
        adapter.AssistantManager = Manager
        with patch.dict(sys.modules, {"addGo": adapter}), patch.object(sys, "argv", [str(SCRIPT), *arguments]), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            runpy.run_path(str(SCRIPT), run_name="__main__")
        return calls

    def test_helper_root_and_absolute_report_are_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report with spaces.txt"
            report.write_text("ordinary line\nFailed compile\nError detail\nExpiredToken\nstatus code: 400\nsource.go:7\n", encoding="utf-8")
            calls = self.execute([str(report)])
            self.assertEqual(calls, [
                ("manager", "goBot", str(SCRIPT.parent) + os.sep),
                ("thread", ["Failed compile", "Error detail", "ExpiredToken", "status code: 400", "source.go:7"]),
            ])
            self.assertEqual(report.read_text().splitlines()[0], "ordinary line")

    def test_relative_report_from_foreign_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            original = os.getcwd()
            try:
                os.chdir(directory)
                Path("report.txt").write_text("normal\nexample.go: Error\n")
                calls = self.execute(["report.txt"])
            finally:
                os.chdir(original)
            self.assertEqual(calls[0], ("manager", "goBot", str(SCRIPT.parent) + os.sep))
            self.assertEqual(calls[1], ("thread", ["example.go: Error"]))

    def test_wrong_argument_count_exits_before_constructing_manager(self):
        for args in [[], ["one", "two"]]:
            with self.subTest(args=args), self.assertRaises(SystemExit) as error:
                self.execute(args)
            self.assertEqual(error.exception.code, 1)
            self.assertEqual(self.last_calls, [])

    def test_missing_report_propagates_file_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                self.execute([str(Path(directory) / "absent.txt")])
            self.assertEqual(self.last_calls, [])


if __name__ == "__main__":
    unittest.main()
