"""Actual stdlib command and isolated failure checks for Go context export."""

import contextlib
import importlib
import io
import logging
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


HELPERS = Path(__file__).resolve().parents[1] / "goHelpers"
ENTRY = HELPERS / "exportContext.py"
sys.path.insert(0, str(HELPERS))
try:
    exporter = importlib.import_module("exportContext")
finally:
    sys.path.pop(0)


class ExportContextTests(unittest.TestCase):
    def launch(self, *arguments, cwd=None):
        return subprocess.run(
            [sys.executable, "-B", "-S", str(ENTRY), *map(str, arguments)],
            cwd=cwd, env={"PATH": os.defpath, "LC_ALL": "C", "PYTHONUTF8": "1"},
            text=True, encoding="utf-8", capture_output=True, timeout=10,
        )

    def source(self, base):
        source = base / "Go source café"
        source.mkdir()
        (source / "main.go").write_text("package demo\nfunc Main() {}\n", encoding="utf-8")
        return source

    def assert_failure(self, result, retained=None):
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
        self.assertLessEqual(len(result.stderr), 800)
        self.assertNotIn("Traceback", result.stderr)
        if retained is not None:
            self.assertIn(str(retained), result.stderr)
            self.assertIn("incomplete output retained", result.stderr)
            self.assertTrue(retained.is_dir())

    def invoke_with_fault(self, source, destination):
        stdout, stderr = io.StringIO(), io.StringIO()
        logging_threshold = logging.root.manager.disable
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = exporter.main([str(source), str(destination)])
        self.assertEqual(logging.root.manager.disable, logging_threshold)
        return subprocess.CompletedProcess([], status, stdout.getvalue(), stderr.getvalue())

    def test_complete_repeatable_exports_preserve_sources_and_prior_context(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = self.source(base)
            nested = source / "nested space"
            nested.mkdir()
            (nested / "café.go").write_text("package demo\nfunc Café() {}\n", encoding="utf-8")
            (source / "aux.go").write_text("package aux\nfunc Helper() {}\n", encoding="utf-8")
            (source / "only_test.go").write_text("package excluded\nfunc Excluded() {}\n")
            (source / "demo_go.txt").write_bytes(b"prior context must survive\n")
            before = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
            artifacts = []
            for name in ("first output", "second output"):
                destination = base / name
                result = self.launch(source, destination, cwd=base)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, str(destination) + "\n")
                self.assertEqual(result.stderr, "")
                self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o700)
                actual = {p.name: p.read_bytes() for p in destination.iterdir()}
                self.assertEqual(set(actual), {"demo_go.txt", "aux_go.txt", "package_map_context.txt",
                                               "directory_tree.txt", "directory_tree_updated.txt",
                                               "projectDirectoryTree_context.txt"})
                mapping = actual["package_map_context.txt"].decode("utf-8")
                self.assertIn("'demo_go.txt' contains ['main.go', 'nested space/café.go']", mapping)
                self.assertIn("'aux_go.txt' contains ['aux.go']", mapping)
                self.assertNotIn("only_test.go", mapping)
                self.assertIn("Go Packages are: aux, and demo\n", actual["directory_tree.txt"].decode("utf-8"))
                self.assertIn("not a faithful filesystem topology", actual["projectDirectoryTree_context.txt"].decode("utf-8"))
                self.assertIn("func Café() {}", actual["demo_go.txt"].decode("utf-8"))
                artifacts.append(actual)
                self.assertEqual({p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}, before)
            self.assertEqual(artifacts[0], artifacts[1])

    def test_help_and_argument_failures_create_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            help_result = self.launch("--help", cwd=base)
            self.assertEqual(help_result.returncode, 0)
            self.assertIn("NEW_OUTPUT_DIR", help_result.stdout)
            for args in ((), ("missing",), ("missing", "output", "extra"), ("", "output")):
                self.assert_failure(self.launch(*args, cwd=base))
            self.assertEqual(list(base.iterdir()), [])

    def test_invalid_source_and_missing_destination_parent_do_not_create_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = self.source(base)
            for invalid in (base / "missing", source / "main.go"):
                destination = base / "new"
                self.assert_failure(self.launch(invalid, destination))
                self.assertFalse(destination.exists())
            self.assert_failure(self.launch(source, base / "missing parent" / "new"))
            self.assertFalse((base / "missing parent").exists())

    def test_existing_entries_including_dangling_links_are_never_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = self.source(base)
            original = (source / "main.go").read_bytes()
            existing_dir = base / "prior directory"
            existing_dir.mkdir()
            (existing_dir / "sentinel").write_bytes(b"keep directory\n")
            existing_file = base / "prior file"
            existing_file.write_bytes(b"keep file\n")
            existing_link = base / "prior link"
            existing_link.symlink_to(source / "main.go")
            dangling = base / "dangling link"
            target = base / "absent target"
            dangling.symlink_to(target)
            for destination in (existing_dir, existing_file, existing_link, dangling):
                self.assert_failure(self.launch(source, destination))
                self.assertTrue(os.path.lexists(destination))
            self.assertEqual((existing_dir / "sentinel").read_bytes(), b"keep directory\n")
            self.assertEqual(existing_file.read_bytes(), b"keep file\n")
            self.assertTrue(existing_link.is_symlink())
            self.assertTrue(dangling.is_symlink())
            self.assertFalse(target.exists())
            self.assertEqual((source / "main.go").read_bytes(), original)

    def test_source_containment_including_parent_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = self.source(base)
            parent_link = base / "source alias"
            parent_link.symlink_to(source, target_is_directory=True)
            for destination in (source / "export", parent_link / "export"):
                self.assert_failure(self.launch(source, destination))
                self.assertFalse((source / "export").exists())
            self.assertTrue(parent_link.is_symlink())

    def test_cyclic_source_and_destination_parent_are_bounded_failures(self):
        for position in ("source", "parent"):
            with self.subTest(position=position), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                source = self.source(base)
                original = (source / "main.go").read_bytes()
                loop = base / "self loop"
                loop.symlink_to(loop.name)
                destination = base / "output" if position == "source" else loop / "output"
                result = self.launch(loop if position == "source" else source, destination)
                self.assert_failure(result)
                self.assertTrue(loop.is_symlink())
                self.assertEqual(os.readlink(loop), loop.name)
                self.assertFalse((base / "output").exists())
                self.assertEqual((source / "main.go").read_bytes(), original)

    def test_no_recognized_non_test_packages_reports_retained_incomplete_folder(self):
        for contents, name in (("package test\n", "only_test.go"), ("not a Go package\n", "invalid.go")):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                source = base / "source"
                source.mkdir()
                (source / name).write_text(contents)
                destination = base / "output"
                self.assert_failure(self.launch(source, destination), destination)
                self.assertEqual(list(destination.iterdir()), [])
                self.assertEqual((source / name).read_text(), contents)

    def test_broken_source_link_fails_without_false_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = self.source(base)
            broken = source / "broken.go"
            broken.symlink_to("absent.go")
            destination = base / "output"
            self.assert_failure(self.launch(source, destination), destination)
            self.assertTrue(broken.is_symlink())
            self.assertFalse((source / "demo_go.txt").exists())

    def test_actual_package_publication_failure_has_no_false_map_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "source"
            source.mkdir()
            original = "package " + "a" * 300 + "\nfunc Example() {}\n"
            (source / "input.go").write_text(original)
            destination = base / "output"
            self.assert_failure(self.launch(source, destination), destination)
            self.assertEqual(list(destination.iterdir()), [])
            self.assertEqual((source / "input.go").read_text(), original)

    def test_case_colliding_package_names_cannot_produce_a_false_complete_map(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = self.source(base)
            (source / "other.go").write_text("package Demo\nfunc Other() {}\n")
            destination = base / "output"
            # Simulate Windows path normalization; this is not Windows runtime qualification.
            with patch.object(exporter.os.path, "normcase", str.casefold):
                self.assert_failure(self.invoke_with_fault(source, destination), destination)
            self.assertFalse((destination / "package_map_context.txt").exists())
            self.assertEqual((source / "other.go").read_text(), "package Demo\nfunc Other() {}\n")

    def test_strict_walk_error_propagates_and_restores_logging(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = self.source(base)
            destination = base / "output"

            def fail_walk(path, **kwargs):
                self.assertIn("onerror", kwargs)
                kwargs["onerror"](PermissionError("synthetic traversal denied"))
                return iter(())

            with patch.object(exporter.getter.os, "walk", fail_walk):
                self.assert_failure(self.invoke_with_fault(source, destination), destination)
            self.assertEqual(list(destination.iterdir()), [])

    def test_tree_walk_failure_after_package_publication_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = self.source(base)
            destination = base / "output"
            actual_walk = exporter.getter.os.walk
            calls = []

            def walk(path, **kwargs):
                calls.append(path)
                if len(calls) == 2:
                    kwargs["onerror"](PermissionError("synthetic tree traversal denied"))
                return actual_walk(path, **kwargs)

            with patch.object(exporter.getter.os, "walk", walk):
                self.assert_failure(self.invoke_with_fault(source, destination), destination)
            self.assertTrue((destination / "demo_go.txt").is_file())
            self.assertTrue((destination / "package_map_context.txt").is_file())
            self.assertFalse((destination / "projectDirectoryTree_context.txt").exists())
            self.assertEqual((source / "main.go").read_text(), "package demo\nfunc Main() {}\n")

    def test_late_artifact_failure_does_not_report_partial_export_as_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = self.source(base)
            destination = base / "output"
            with patch.object(exporter.directoryTree, "append_files_with_blurb",
                              side_effect=OSError("synthetic final artifact\nfailure")):
                self.assert_failure(self.invoke_with_fault(source, destination), destination)
            self.assertTrue((destination / "demo_go.txt").is_file())
            self.assertTrue((destination / "directory_tree_updated.txt").is_file())
            self.assertFalse((destination / "projectDirectoryTree_context.txt").exists())
            self.assertEqual((source / "main.go").read_text(), "package demo\nfunc Main() {}\n")


if __name__ == "__main__":
    unittest.main()
