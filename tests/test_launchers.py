"""Actual copied launchers with inert command adapters; no provider or Go runs."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
STUB = '''#!/usr/bin/python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
if name == 'python3' and (not args or pathlib.Path(args[0]).parent != pathlib.Path(os.environ['GOPILOT_FIXTURE_HELPER'])):
    sys.exit(99)
with open(os.environ['GOPILOT_FIXTURE_TRACE'], 'a') as stream:
    stream.write(json.dumps({'command': name, 'args': args, 'cwd': os.getcwd()}) + '\\n')
if name == 'python3':
    script = pathlib.Path(args[0]).name
    if script == 'main.py': sys.exit(int(os.environ.get('GOPILOT_FIXTURE_MAIN_EXIT', '0')))
    if script == 'errorParser.py':
        print('View response here: https://example.invalid/inert-thread')
        sys.exit(int(os.environ.get('GOPILOT_FIXTURE_PARSER_EXIT', '0')))
    if script == 'htmlParser.py':
        status = int(os.environ.get('GOPILOT_FIXTURE_HTML_EXIT', '0'))
        print('inert HTML failure' if status else 'inert HTML context saved', file=sys.stderr if status else sys.stdout)
        sys.exit(status)
    if script != 'chatParse.py': sys.exit(99)
else:
    print('inert example.go diagnostic')
    sys.exit(int(os.environ.get('GOPILOT_FIXTURE_GO_EXIT', '0')))
'''


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo = root / "checkout with spaces"
        self.helper = self.repo / "goHelpers"
        self.helper.mkdir(parents=True)
        for filename in ["ezRun.sh", "goHelpers/all_run.sh", "goHelpers/makefile", "goHelpers/scrapeWeb.sh", "goHelpers/htmlParser.py"]:
            shutil.copyfile(ROOT / filename, self.repo / filename)
        self.cwd = root / "caller Go project"
        self.cwd.mkdir()
        self.context = root / "separate context project"
        self.context.mkdir()
        self.trace = root / "trace.jsonl"
        adapter = root / "inert commands"
        adapter.mkdir()
        for name in ["python3", "go", "golangci-lint"]:
            stub = adapter / name
            stub.write_text(STUB)
            stub.chmod(0o755)
        self.env = os.environ.copy()
        self.env.update({"PATH": str(adapter) + os.pathsep + self.env["PATH"],
                         "GOPILOT_FIXTURE_HELPER": str(self.helper),
                         "GOPILOT_FIXTURE_TRACE": str(self.trace)})
        # HOME/CODEX_HOME are deliberately neither replaced nor changed.

    def calls(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()] if self.trace.exists() else []

    def run_script(self, filename, arguments, **environment):
        return subprocess.run(["bash", str(self.repo / filename), *arguments], cwd=self.cwd,
                              env={**self.env, **environment}, capture_output=True, text=True, timeout=10)

    def run_outer(self, arguments, **environment):
        # Refuse to run the old outer script: its absolute legacy calls and
        # default thread truncation cannot be intercepted by PATH adapters.
        source = (self.repo / "ezRun.sh").read_text()
        self.assertNotIn("~/projects/goHelper", source, "unsafe baseline outer body not executed")
        self.assertNotIn("${HOME}/projects/goHelper", source, "unsafe baseline outer body not executed")
        return self.run_script("ezRun.sh", arguments, **environment)

    def sentinel(self):
        path = self.helper / "results" / "chatThreads.txt"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"previous thread sentinel\n")
        return path

    def test_help_is_successful_and_has_no_side_effects(self):
        for filename in ["ezRun.sh", "goHelpers/all_run.sh"]:
            for flag in ["-h", "--help"]:
                with self.subTest(filename=filename, flag=flag):
                    result = self.run_script(filename, [flag])
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("Usage:", result.stdout)
                    self.assertEqual(self.calls(), [])
                    self.assertFalse((self.helper / "results").exists())

    def test_helper_failure_is_not_masked(self):
        result = self.run_script("goHelpers/all_run.sh", ["-d", str(self.context)], GOPILOT_FIXTURE_MAIN_EXIT="37")
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertEqual(self.calls()[0]["args"], [str(self.helper / "main.py"), str(self.context), str(self.helper), "false", "false"])

    def test_scrape_uses_adjacent_helper_exact_url_and_preserves_caller_cwd(self):
        for url in ["https://example.dev/a path?q=%20&next=$literal#fragment", "-literal-url"]:
            with self.subTest(url=url):
                result = self.run_script("goHelpers/scrapeWeb.sh", [url], CDPATH=str(self.context))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "inert HTML context saved\n")
                self.assertEqual(result.stderr, "")
                self.assertEqual(self.calls()[-1], {"command": "python3", "args": [str(self.helper / "htmlParser.py"), url, str(self.helper)], "cwd": str(self.cwd)})
                self.assertFalse((self.helper / "results").exists())

    def test_scrape_preserves_helper_failure_status_and_streams(self):
        for status in [1, 42, 127]:
            with self.subTest(status=status):
                result = self.run_script("goHelpers/scrapeWeb.sh", ["https://example.dev"], GOPILOT_FIXTURE_HTML_EXIT=str(status))
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "inert HTML failure\n")
                self.assertEqual(len(self.calls()), [1, 42, 127].index(status) + 1)

    def test_scrape_help_and_invalid_arguments_do_not_dispatch(self):
        for flag in ["-h", "--help"]:
            result = self.run_script("goHelpers/scrapeWeb.sh", [flag])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Usage:", result.stdout)
            self.assertEqual(result.stderr, "")
        for args in [[], ["one", "two"], [""], [" \t\n"]]:
            with self.subTest(args=args):
                result = self.run_script("goHelpers/scrapeWeb.sh", args)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn("Usage:", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_outer_helper_failure_stops_before_cleanup_checks_or_parsers(self):
        sentinel = self.sentinel()
        result = self.run_outer(["-r", "true", "-n", "true", "-t", "true"], GOPILOT_FIXTURE_MAIN_EXIT="37")
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertEqual(sentinel.read_bytes(), b"previous thread sentinel\n")
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(Path(self.calls()[0]["args"][0]).name, "main.py")

    def test_native_paths_and_caller_go_cwd_with_default_outputs(self):
        result = self.run_outer(["-d", str(self.context), "-r", "true", "-n", "true", "-t", "true", "-x", "false"])
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertEqual(calls[0]["args"], [str(self.helper / "main.py"), str(self.context), str(self.helper), "false", "false"])
        self.assertEqual([call["command"] for call in calls], ["python3", "go", "python3", "golangci-lint", "python3", "go", "python3", "python3"])
        self.assertTrue(all(call["cwd"] == str(self.cwd) for call in calls))
        for filename in ["codeRun.txt", "lintOutput.txt", "testOutput.txt"]:
            self.assertIn("inert example.go", (self.helper / "results" / filename).read_text())
        for call in calls:
            if call["command"] == "python3": self.assertEqual(Path(call["args"][0]).parent, self.helper)

    def test_custom_output_paths_and_thread_cleanup_switch(self):
        for clear in ["false", "true"]:
            with self.subTest(clear=clear):
                threads = self.helper / "results" / "chatThreads.txt"
                threads.parent.mkdir(exist_ok=True)
                threads.write_bytes(b"sentinel\n")
                outputs = [self.cwd / (name + " with spaces.txt") for name in ["code", "lint", "test"]]
                args = ["-r", "true", "-n", "true", "-t", "true", "-x", clear]
                for option, path in zip(["-c", "-l", "-o"], outputs): args.extend([option, str(path)])
                result = self.run_outer(args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(all(path.exists() for path in outputs))
                self.assertEqual(threads.read_text().startswith("sentinel"), clear == "false")

    def test_invalid_arguments_never_create_results_or_call_commands(self):
        for filename, options in [("ezRun.sh", ["-u", "-a", "-r", "-n", "-t", "-x"]), ("goHelpers/all_run.sh", ["-u", "-a"])]:
            for arguments in [[option, "yes"] for option in options] + [[option] for option in ["-d", *options]] + [["-d", ""], ["-z"], ["unexpected"], ["--", "unexpected"]]:
                with self.subTest(filename=filename, arguments=arguments):
                    result = self.run_outer(arguments) if filename == "ezRun.sh" else self.run_script(filename, arguments)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(self.calls(), [])
                    self.assertFalse((self.helper / "results").exists())

    def test_invalid_context_stops_before_results_commands_and_thread_cleanup(self):
        missing = self.cwd / "missing context"
        regular_file = self.cwd / "not a directory"
        regular_file.write_bytes(b"context sentinel")
        for filename in ["ezRun.sh", "goHelpers/all_run.sh"]:
            for context in [missing, regular_file]:
                with self.subTest(filename=filename, context=context):
                    args = ["-d", str(context)]
                    result = self.run_outer(args) if filename == "ezRun.sh" else self.run_script(filename, args)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(self.calls(), [])
                    self.assertFalse((self.helper / "results").exists())
        threads = self.sentinel()
        before = threads.stat().st_mtime_ns
        result = self.run_outer(["-d", str(missing), "-r", "true"])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(threads.read_bytes(), b"previous thread sentinel\n")
        self.assertEqual(threads.stat().st_mtime_ns, before)
        self.assertEqual(self.calls(), [])

    def test_disabled_cleanup_preserves_existing_log_without_touching_it(self):
        threads = self.sentinel()
        old_time = 1_600_000_000_000_000_000
        os.utime(threads, ns=(old_time, old_time))
        result = self.run_outer(["-x", "false"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(threads.read_bytes(), b"previous thread sentinel\n")
        self.assertEqual(threads.stat().st_mtime_ns, old_time)

    def test_go_failure_still_reaches_error_parser_and_parser_failure_propagates(self):
        result = self.run_outer(["-t", "true"], GOPILOT_FIXTURE_GO_EXIT="1", GOPILOT_FIXTURE_PARSER_EXIT="43")
        self.assertEqual(result.returncode, 43)
        calls = self.calls()
        self.assertEqual([Path(call["args"][0]).name for call in calls if call["command"] == "python3"], ["main.py", "errorParser.py"])

    @unittest.skipUnless(shutil.which("make"), "make is unavailable; named-target execution requires local verification with Make")
    def test_make_targets_preserve_maintained_wrapper(self):
        before = (self.helper / "all_run.sh").read_bytes()
        result = subprocess.run(["make", "-C", str(self.helper), "create_script", "clean"], cwd=self.cwd,
                                env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.helper / "all_run.sh").exists())
        self.assertEqual((self.helper / "all_run.sh").read_bytes(), before)
        self.assertEqual(self.calls(), [])
        result = subprocess.run(["make", "-f", "goHelpers/makefile", "create_script", "clean"], cwd=self.repo,
                                env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.helper / "all_run.sh").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
