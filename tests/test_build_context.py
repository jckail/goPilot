"""Real deterministic archives, native execution and publication failure checks."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


HELPERS = Path(__file__).resolve().parents[1] / "goHelpers"
ENTRY = HELPERS / "buildContext.py"
spec = importlib.util.spec_from_file_location("build_context", ENTRY)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BuildContextTests(unittest.TestCase):
    def build(self, *arguments, cwd=None):
        return subprocess.run([sys.executable, "-B", "-S", str(ENTRY), *map(str, arguments)],
                              cwd=cwd, env={"PATH": os.defpath}, text=True,
                              encoding="utf-8", capture_output=True, timeout=10)

    def call(self, destination):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = builder.main([str(destination)])
        return status, out.getvalue(), err.getvalue()

    def assert_failure(self, result):
        status, out, err = result
        self.assertEqual(status, 1)
        self.assertEqual(out, "")
        self.assertEqual(len(err.splitlines()), 1)
        self.assertLessEqual(len(err), 800)
        self.assertNotIn("Traceback", err)

    def test_archive_reproducibility_inventory_metadata_and_embedded_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            copied = base / "helpers"
            copied.mkdir()
            for name in reversed(builder.MODULES):
                (copied / name).write_bytes((HELPERS / name).read_bytes())
                os.utime(copied / name, (1000, 1000))
            first = builder.archive_payload(copied)
            for name in builder.MODULES:
                os.utime(copied / name, (2000, 2000))
            with patch.object(builder, "MODULES", tuple(reversed(builder.MODULES))):
                second = builder.archive_payload(copied)
            self.assertEqual(first, second)
            self.assertTrue(first.startswith(b"#!/usr/bin/env -S python3 -I -B -S\n"))
            with zipfile.ZipFile(io.BytesIO(first)) as archive:
                self.assertEqual(archive.namelist(), ["__main__.py", "directoryTree.py", "exportContext.py", "getter.py", "manifest.json"])
                self.assertEqual(archive.comment, b"")
                manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(manifest["format"], 1)
                self.assertEqual(archive.read("__main__.py"), builder.BOOTSTRAP)
                self.assertEqual(manifest["bootstrapSha256"], hashlib.sha256(builder.BOOTSTRAP).hexdigest())
                for name in builder.MODULES:
                    data = (HELPERS / name).read_bytes()
                    self.assertEqual(archive.read(name), data)
                    self.assertEqual(manifest["modules"][name], hashlib.sha256(data).hexdigest())
                for info in archive.infolist():
                    self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                    self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                    self.assertEqual(info.create_system, 3)
                    self.assertEqual(info.external_attr, 0o100644 << 16)
                    self.assertEqual((info.extra, info.comment), (b"", b""))

    def test_two_real_builds_and_native_isolated_archive_outside_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            first, second = base / "first command", base / "second command"
            for target in [first, second]:
                result = self.build(target, cwd=base)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, str(target) + "\n")
                self.assertEqual(result.stderr, "")
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o700)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            poison = base / "poison"
            poison.mkdir()
            for name in ["exportContext.py", "getter.py", "directoryTree.py", "sitecustomize.py"]:
                (poison / name).write_text("raise RuntimeError('outside module must not load')\n")
            env = {"PATH": os.defpath, "PYTHONPATH": str(poison), "PYTHONUTF8": "1"}

            def run(*arguments):
                return subprocess.run([str(first), *map(str, arguments)], cwd=poison, env=env,
                                      text=True, encoding="utf-8", capture_output=True, timeout=10)

            help_result = run("--help")
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertIn("NEW_OUTPUT_DIR", help_result.stdout)
            source = base / "Go source café"
            (source / "nested space").mkdir(parents=True)
            sources = {"main.go": b"package demo\nfunc Main() {}\n",
                       "nested space/other.go": b"package other\nfunc Other() {}\n"}
            for name, data in sources.items():
                (source / name).write_bytes(data)
            output = base / "export"
            result = run(source, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, str(output) + "\n")
            self.assertEqual(result.stderr, "")
            self.assertEqual(set(path.name for path in output.iterdir()),
                             {"demo_go.txt", "other_go.txt", "package_map_context.txt", "directory_tree.txt",
                              "directory_tree_updated.txt", "projectDirectoryTree_context.txt"})
            self.assertIn("└── main.go", (output / "directory_tree.txt").read_text())
            previous = {path.name: path.read_bytes() for path in output.iterdir()}
            refused = run(source, output)
            self.assertEqual(refused.returncode, 1)
            self.assertEqual(refused.stdout, "")
            self.assertEqual({path.name: path.read_bytes() for path in output.iterdir()}, previous)
            for name, data in sources.items():
                self.assertEqual((source / name).read_bytes(), data)
            self.assertFalse(list(base.glob(".gopilot-archive-*")))
            self.assertFalse(list(poison.rglob("__pycache__")))

    def test_builder_help_bad_arguments_and_missing_parent_do_not_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            self.assertEqual(self.build("--help", cwd=base).returncode, 0)
            for args in [(), ("",), (base / "missing" / "out",), (base / "out", "extra")]:
                with self.subTest(args=args):
                    result = self.build(*args, cwd=base)
                    self.assert_failure((result.returncode, result.stdout, result.stderr))
            self.assertEqual(list(base.iterdir()), [])

    def test_existing_files_directories_links_and_dangling_links_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            regular = base / "file"
            regular.write_bytes(b"previous")
            folder = base / "folder"
            folder.mkdir()
            link = base / "link"
            link.symlink_to(regular)
            dangling = base / "dangling"
            dangling.symlink_to(base / "absent")
            for target in [regular, folder, link, dangling]:
                self.assert_failure(self.call(target))
            self.assertEqual(regular.read_bytes(), b"previous")
            self.assertTrue(link.is_symlink())
            self.assertTrue(dangling.is_symlink())
            self.assertTrue(folder.is_dir())
            self.assertFalse(list(base.glob(".gopilot-archive-*")))

    def test_source_containment_direct_and_through_parent_link_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            alias = base / "source alias"
            alias.symlink_to(HELPERS, target_is_directory=True)
            name = ".test-forbidden-context-artifact"
            self.assertFalse(os.path.lexists(HELPERS / name))
            for target in [HELPERS / name, alias / name]:
                self.assert_failure(self.call(target))
            self.assertFalse(os.path.lexists(HELPERS / name))

    def test_cyclic_parent_is_bounded_and_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "loop").symlink_to(base / "loop")
            self.assert_failure(self.call(base / "loop" / "artifact"))
            self.assertTrue((base / "loop").is_symlink())

    def test_missing_or_invalid_module_fails_before_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            helpers = base / "source" / "goHelpers"
            helpers.mkdir(parents=True)
            for name in builder.MODULES:
                (helpers / name).write_bytes((HELPERS / name).read_bytes())
            target = base / "artifact"
            (helpers / "getter.py").unlink()
            with patch.object(builder, "__file__", str(helpers / "buildContext.py")):
                self.assert_failure(self.call(target))
                (helpers / "getter.py").write_bytes(b"invalid syntax !\n")
                self.assert_failure(self.call(target))
            self.assertFalse(target.exists())
            self.assertFalse(list(base.glob(".gopilot-archive-*")))

    def test_partial_write_short_write_and_close_failures_remove_owned_stage(self):
        original = builder.tempfile.NamedTemporaryFile

        class FaultHandle:
            def __init__(self, handle, fault):
                self.handle, self.fault = handle, fault
                self.name = handle.name

            def __enter__(self):
                self.handle.__enter__()
                return self

            def write(self, data):
                if self.fault in ("write", "short"):
                    self.handle.write(data[:4])
                    if self.fault == "write":
                        raise OSError("synthetic partial write")
                    return 4
                return self.handle.write(data)

            def fileno(self):
                return self.handle.fileno()

            def __exit__(self, *arguments):
                self.handle.__exit__(*arguments)
                if self.fault == "close":
                    raise OSError("synthetic close failure")

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for fault in ["write", "short", "close"]:
                target = base / fault
                with patch.object(builder.tempfile, "NamedTemporaryFile",
                                  side_effect=lambda **kwargs: FaultHandle(original(**kwargs), fault)):
                    self.assert_failure(self.call(target))
                self.assertFalse(target.exists())
                self.assertFalse(list(base.glob(".gopilot-archive-*")))

    def test_exclusive_publication_race_preserves_complete_foreign_target(self):
        original = builder.os.link
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            target = base / "artifact"

            def race(stage, destination):
                self.assertEqual(stat.S_IMODE(Path(stage).stat().st_mode), 0o700)
                with zipfile.ZipFile(stage) as archive:
                    self.assertEqual(archive.read("__main__.py"), builder.BOOTSTRAP)
                Path(destination).write_bytes(b"foreign race winner")
                original(stage, destination)

            with patch.object(builder.os, "link", side_effect=race):
                self.assert_failure(self.call(target))
            self.assertEqual(target.read_bytes(), b"foreign race winner")
            self.assertFalse(list(base.glob(".gopilot-archive-*")))

    def test_unsupported_link_fails_without_partial_output_or_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            target = base / "artifact"
            with patch.object(builder.os, "link", side_effect=OSError("unsupported hard link")):
                self.assert_failure(self.call(target))
            self.assertFalse(target.exists())
            self.assertFalse(list(base.glob(".gopilot-archive-*")))

    def test_cleanup_after_publication_reports_complete_artifact_and_owned_stage(self):
        original = Path.unlink
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            target = base / "artifact"

            def refuse_stage(path, *args, **kwargs):
                if path.name.startswith(".gopilot-archive-"):
                    raise OSError("cleanup\nrefused " + "x" * 4000)
                return original(path, *args, **kwargs)

            with patch.object(Path, "unlink", refuse_stage):
                result = self.call(target)
            self.assert_failure(result)
            self.assertIn("complete artifact published:", result[2])
            self.assertIn("owned staging file retained:", result[2])
            stages = list(base.glob(".gopilot-archive-*"))
            self.assertEqual(len(stages), 1)
            self.assertEqual(stages[0].read_bytes(), target.read_bytes())
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o700)
            stages[0].unlink()
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(archive.read("__main__.py"), builder.BOOTSTRAP)


if __name__ == "__main__":
    unittest.main()
