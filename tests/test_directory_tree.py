"""Actual-module checks for legacy tree file-suffix conversion."""

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "directory_tree", Path(__file__).resolve().parents[1] / "goHelpers" / "directoryTree.py"
)
directory_tree = importlib.util.module_from_spec(spec)
spec.loader.exec_module(directory_tree)


class TreeSuffixTests(unittest.TestCase):
    def convert(self, content):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.txt"
            output = Path(directory) / "output.txt"
            source.write_bytes(content)
            directory_tree.replace_suffix_in_file(str(source), str(output))
            self.assertEqual(source.read_bytes(), content)
            return output.read_bytes()

    def test_actual_generated_tree_preserves_metadata_directories_and_non_go_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project.go"
            root.mkdir()
            nested = root / "cache.go"
            nested.mkdir()
            names = ["main.go", "double.go.go", "notes.go.md", "assets.golden", "café file.go"]
            for name in names:
                (root / name).write_bytes(b"unchanged synthetic source\n")
            (nested / "nested.go").write_bytes(b"nested source\n")
            source = Path(directory) / "tree.txt"
            output = Path(directory) / "legacy.txt"
            directory_tree.save_dir_tree_to_file(str(root), str(source), packages=["pkg.go"])
            original = source.read_bytes()
            directory_tree.replace_suffix_in_file(str(source), str(output))
            actual = output.read_text(encoding="utf-8")
            self.assertIn("called: project.go's", actual)
            self.assertIn("Go Packages are: , and pkg.go\n", actual)
            self.assertIn("project.go/\n", actual)
            self.assertIn("cache.go/\n", actual)
            for name in ["main_go.txt", "double.go_go.txt", "notes.go.md", "assets.golden", "café file_go.txt", "nested_go.txt"]:
                self.assertEqual(sum(line.endswith(name) for line in actual.splitlines()), 1)
            self.assertEqual(source.read_bytes(), original)
            for name in names:
                self.assertEqual((root / name).read_bytes(), b"unchanged synthetic source\n")
            self.assertEqual((nested / "nested.go").read_bytes(), b"nested source\n")

    def test_only_tree_file_entries_change_even_when_metadata_ends_in_go(self):
        before = (
            "Package metadata: example.go\n"
            "This sentence mentions example.go\n"
            "bare.go\n"
            "root.go/\n"
            "├── metadata.go\n"
            "├── directory.go/\n"
            "│   ├── first.go\n"
            "│   │   └── second.go.go\n"
            "│   └── notes.go.md\n"
        )
        expected = before.replace("│   ├── first.go\n", "│   ├── first_go.txt\n").replace(
            "│   │   └── second.go.go\n", "│   │   └── second.go_go.txt\n"
        )
        self.assertEqual(self.convert(before.encode("utf-8")), expected.encode("utf-8"))

    def test_unicode_spaces_and_mixed_line_endings_are_byte_preserved(self):
        before = "Header café.go\r\n├── café.go/\r\n│   ├── café file.go\r\n│   ├── archive.go.md\n│   └── final.go".encode("utf-8")
        expected = "Header café.go\r\n├── café.go/\r\n│   ├── café file_go.txt\r\n│   ├── archive.go.md\n│   └── final_go.txt".encode("utf-8")
        self.assertEqual(self.convert(before), expected)

    def test_empty_and_non_entry_content_is_unchanged(self):
        for content in [b"", b"documentation.go\nfile.golden\r\n", "├── directory.go/\n│   ├── upper.GO\n│   └── trailing.go \n".encode("utf-8")]:
            with self.subTest(content=content):
                self.assertEqual(self.convert(content), content)


class TreeOrderTests(unittest.TestCase):
    def test_generated_tree_and_converted_artifact_are_stable_across_walk_order(self):
        sources = {
            "apple.go": b"package main\n",
            "zebra.go": b"package main\nfunc Z() {}\n",
            "ignore.go": b"package ignored\n",
            "alpha/m.go": b"package alpha\n",
            "alpha/nested/a.txt": b"note\n",
            "alpha/nested/b.go": b"package nested\n",
            "beta/a.go": b"package beta\n",
            "beta/z.go": b"package beta\nfunc Z() {}\n",
            "beta/ignore.go": b"package beta\nfunc Hidden() {}\n",
            ".hidden/visible-in-hidden.go": b"package hidden\n",
            "skipdir/nope.go": b"package skip\n",
        }
        expected = (
            "This go project is called: proj's here is it's current directory tree.\n"
            "proj's current Go Packages are: alpha, and beta\n"
            "\n"
            "proj/\n"
            "│   ├── apple.go\n"
            "│   └── zebra.go\n"
            "├── alpha/\n"
            "│   └── m.go\n"
            "│   ├── empty/\n"
            "│   ├── nested/\n"
            "│   │   ├── a.txt\n"
            "│   │   └── b.go\n"
            "├── beta/\n"
            "│   ├── a.go\n"
            "│   └── z.go\n"
        )
        blurb = "map each terminal .go tree entry onto the _go.txt view"

        def controlled_walk(path, reverse):
            # Descent must honor in-place edits to dirs, the same way os.walk does.
            current = Path(path)
            dirs = sorted((entry.name for entry in current.iterdir() if entry.is_dir()), reverse=reverse)
            files = sorted((entry.name for entry in current.iterdir() if entry.is_file()), reverse=reverse)
            yield str(current), dirs, files
            for dirname in dirs:
                yield from controlled_walk(current / dirname, reverse)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "proj"
            root.mkdir()
            (root / "alpha" / "empty").mkdir(parents=True)
            for name, content in sources.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            originals = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}

            artifacts = []
            for reverse in (False, True):
                tree_path = Path(directory) / f"tree-{reverse}.txt"
                converted_path = Path(directory) / f"converted-{reverse}.txt"
                combined_path = Path(directory) / f"combined-{reverse}.txt"
                start = str(root) if reverse else str(root) + os.sep
                def walk_in_order(path, topdown=True, onerror=None, followlinks=False, reverse=reverse):
                    return controlled_walk(path, reverse)

                with patch.object(directory_tree.os, "walk", side_effect=walk_in_order):
                    directory_tree.save_dir_tree_to_file(
                        start,
                        str(tree_path),
                        packages=["alpha", "beta"],
                        exclude=["skipdir", "ignore.go"],
                    )
                tree_bytes = tree_path.read_bytes()
                directory_tree.replace_suffix_in_file(str(tree_path), str(converted_path))
                self.assertEqual(tree_path.read_bytes(), tree_bytes)
                combined = directory_tree.append_files_with_blurb(
                    str(tree_path), str(converted_path), str(combined_path), blurb
                )
                self.assertEqual(combined, str(combined_path.resolve()))
                artifacts.append((tree_bytes, converted_path.read_bytes(), combined_path.read_bytes()))
                for path, content in originals.items():
                    self.assertEqual(path.read_bytes(), content)

            self.assertEqual(artifacts[0], artifacts[1])
            tree_bytes, converted_bytes, combined_bytes = artifacts[0]
            rendered = tree_bytes.decode("utf-8")
            self.assertEqual(rendered, expected)
            for excluded in (".hidden", "visible-in-hidden.go", "skipdir", "nope.go", "ignore.go"):
                self.assertNotIn(excluded, rendered)
            suffix = TreeSuffixTests()
            self.assertEqual(converted_bytes, suffix.convert(expected.encode("utf-8")))
            converted_text = converted_bytes.decode("utf-8")
            self.assertIn("│   ├── apple_go.txt\n", converted_text)
            self.assertIn("│   │   ├── a.txt\n", converted_text)
            self.assertIn("│   ├── empty/\n", converted_text)
            self.assertEqual(
                combined_bytes.decode("utf-8"),
                expected + "\n" + blurb + "\n\n" + converted_text,
            )


if __name__ == "__main__":
    unittest.main()
