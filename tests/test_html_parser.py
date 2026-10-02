"""Actual HTML-helper entry with inert HTTP and HTML dependency boundaries."""

import contextlib
import hashlib
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
EXPECTED_NAME = "web-example-dev-docs-" + hashlib.sha256(URL.encode("utf-8")).hexdigest() + "_context.txt"


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
                        output = helper / "additionalcontext" / EXPECTED_NAME
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
            self.assertEqual((context / EXPECTED_NAME).read_text(), EXPECTED)

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

    def test_other_tld_entry_now_produces_context(self):
        with tempfile.TemporaryDirectory() as directory:
            namespace = self.execute(["https://example.org/docs", directory])
            name = namespace["generate_filename_from_url"]("https://example.org/docs")
            self.assertEqual((Path(directory) / "additionalcontext" / (name + "_context.txt")).read_text(), EXPECTED)

    def test_exact_url_identity_and_default_resources_are_distinct(self):
        import ast
        with tempfile.TemporaryDirectory() as directory:
            namespace = self.execute([URL, directory])
            name = namespace["generate_filename_from_url"]
            variants = [
                "https://first.dev/reference", "https://second.dev/reference",
                "http://first.dev/reference", "https://first.dev:443/reference",
                "https://first.dev/reference?q=1", "https://first.dev/reference?q=2",
                "https://first.dev/reference#one", "https://first.dev/reference#two",
                "https://first.dev/%72eference", "https://first.dev/reference/",
                "https://pkg.go.dev/github.com/hamba/avro/v2",
                "https://github.com/hamba/avro/v2",
            ]
            names = [name(url) for url in variants]
            self.assertEqual(len(set(names)), len(variants))
            self.assertEqual(name(variants[0]), names[0])
            tree = ast.parse((SCRIPT.parent / "main.py").read_text())
            resources = next(ast.literal_eval(node.value) for node in ast.walk(tree)
                if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "webreources" for target in node.targets))
            self.assertEqual(len(resources), 8)
            self.assertEqual(len({name(url) for url in resources}), 8)

    def test_names_are_bounded_portable_and_confined_for_long_unicode_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            namespace = self.execute([URL, directory])
            for url in ["https://long.dev/" + "a" * 500, "https://例え.org/" + "雪 /\\?x=\x01" * 100]:
                with self.subTest(url_prefix=url[:30]):
                    name = namespace["generate_filename_from_url"](url)
                    self.assertRegex(name, r"^web-[a-zA-Z0-9_-]{1,80}-[0-9a-f]{64}$")
                    self.assertTrue(name.endswith(hashlib.sha256(url.encode("utf-8")).hexdigest()))
                    self.assertLessEqual(len((name + "_context.txt").encode("ascii")), 161)
                    output = Path(directory) / "additionalcontext" / (name + "_context.txt")
                    self.assertEqual(output.parent, Path(directory) / "additionalcontext")
                    # Execute actual fetch/write as well as inspecting its filename.
                    self.execute([url, directory])
                    self.assertEqual(output.read_text(), EXPECTED)

    def test_two_urls_keep_both_contexts_and_repeated_url_updates_only_its_file(self):
        with tempfile.TemporaryDirectory() as directory:
            first = "https://first.dev/reference"
            second = "https://second.dev/reference"
            namespace = self.execute([first, directory])
            name = namespace["generate_filename_from_url"]
            context = Path(directory) / "additionalcontext"
            first_output = context / (name(first) + "_context.txt")
            first_output.write_text("first context sentinel")
            legacy = context / "reference_context.txt"
            legacy.write_text("legacy retained")
            self.execute([second, directory])
            self.assertEqual(first_output.read_text(), "first context sentinel")
            self.assertEqual((context / (name(second) + "_context.txt")).read_text(), EXPECTED)
            self.execute([second, directory])
            self.assertEqual(len(list(context.iterdir())), 3)
            self.assertEqual(legacy.read_text(), "legacy retained")


if __name__ == "__main__":
    unittest.main()
