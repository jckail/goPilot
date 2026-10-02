"""Actual HTML-helper entry with inert HTTP and HTML dependency boundaries."""

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


SCRIPT = Path(__file__).resolve().parents[1] / "goHelpers" / "htmlParser.py"
URL = "https://example.dev/docs"
HTML = "<body><p>Reference</p><p>func Example() {} ¶</p></body>"
EXPECTED = "Reference\n\nfunc Example() {}"


class HtmlEntryTests(unittest.TestCase):
    def execute(self, arguments, *, main=True, failure=None):
        self.calls = []
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        requests = types.ModuleType("requests")
        requests.HTTPError = type("HTTPError", (Exception,), {})
        def get(url):
            self.calls.append(("get", url))
            if failure == "generic": raise RuntimeError("synthetic fetch failure")
            def check_status():
                if failure == "http": raise requests.HTTPError("synthetic HTTP failure")
            return types.SimpleNamespace(text=HTML, raise_for_status=check_status)
        requests.get = get
        bs4 = types.ModuleType("bs4")
        def soup(content, parser):
            self.calls.append(("parse", content, parser))
            if failure == "parse": raise ValueError("synthetic parsing failure")
            # The adapter supplies a small document structure. Actual production
            # extraction/formatting code runs; real BeautifulSoup is not qualified.
            body = types.SimpleNamespace(descendants=["Reference", types.SimpleNamespace(name="p"), "func Example() {} ¶"])
            return types.SimpleNamespace(body=body, find_all=lambda *args, **kwargs: [])
        bs4.BeautifulSoup = soup
        with patch.dict(sys.modules, {"requests": requests, "bs4": bs4}), patch.object(sys, "argv", [str(SCRIPT), *arguments]), contextlib.redirect_stdout(self.stdout), contextlib.redirect_stderr(self.stderr):
            namespace = runpy.run_path(str(SCRIPT), run_name="__main__" if main else "inert_helper")
            if not main:
                namespace["fetchWebData"](*arguments)
            return namespace

    def test_actual_entry_creates_portable_context_for_helper_paths_with_spaces(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / "helper with spaces"
            helper.mkdir()
            original = os.getcwd()
            try:
                os.chdir(directory)
                for suffix in ["", os.sep]:
                    with self.subTest(suffix=suffix):
                        self.execute([URL, str(helper) + suffix])
                        output = helper / "additionalcontext" / "docs_context.txt"
                        self.assertEqual(output.read_text(), EXPECTED)
                        self.assertEqual(self.calls, [("get", URL), ("parse", HTML, "html.parser")])
                        self.assertIn(str(output), self.stdout.getvalue())
                        self.assertEqual(self.stderr.getvalue(), "")
            finally:
                os.chdir(original)

    def test_existing_directory_and_sentinel_are_preserved_for_direct_caller(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / "helper with spaces"
            context = helper / "additionalcontext"
            context.mkdir(parents=True)
            sentinel = context / "other_context.txt"
            sentinel.write_bytes(b"preserved existing context\n")
            self.execute([URL, str(helper)], main=False)
            self.assertEqual(sentinel.read_bytes(), b"preserved existing context\n")
            self.assertEqual((context / "docs_context.txt").read_text(), EXPECTED)

    def test_wrong_argument_count_reports_usage_without_fetch_or_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / "absent helper"
            for args in [[], [URL], [URL, str(helper), "extra"]]:
                with self.subTest(args=args):
                    with self.assertRaises(SystemExit) as error:
                        self.execute(args)
                    self.assertEqual(error.exception.code, 1)
                    self.assertIn("Usage: python htmlParser.py <URL> <helper-directory>", self.stderr.getvalue())
                    self.assertEqual(self.calls, [])
                    self.assertFalse(helper.exists())

    def test_fetch_failures_preserve_existing_return_without_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            for failure, prefix in [("http", "HTTP error occurred:"), ("generic", "Other error occurred:")]:
                with self.subTest(failure=failure):
                    helper = Path(directory) / failure
                    helper.mkdir()
                    self.execute([URL, str(helper)], failure=failure)
                    self.assertEqual(self.calls, [("get", URL)])
                    self.assertIn(prefix, self.stdout.getvalue())
                    self.assertEqual(list(helper.iterdir()), [])

    def test_processing_failure_creates_no_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / "helper"
            helper.mkdir()
            with self.assertRaisesRegex(ValueError, "synthetic parsing failure"):
                self.execute([URL, str(helper)], failure="parse")
            self.assertFalse((helper / "additionalcontext").exists())

    def test_filename_failure_creates_no_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / "helper"
            helper.mkdir()
            # The legacy .com/.dev filename rule is intentionally unchanged.
            with self.assertRaises(IndexError):
                self.execute(["https://example.invalid/docs", str(helper)])
            self.assertFalse((helper / "additionalcontext").exists())


if __name__ == "__main__":
    unittest.main()
