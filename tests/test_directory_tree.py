"""Actual-module checks for legacy tree file-suffix conversion."""

import importlib.util
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
    def test_multilevel_tree_and_combined_context_ignore_enumeration_order(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "project"
            sources = {
                "z.go": b"root z\n", "a.go": b"root a\n",
                "alpha/z.go": b"alpha z\n", "alpha/a.go": b"alpha a\n",
                "alpha/deep/café.go": b"deep source\n",
                "beta/b.go": b"beta source\n",
                ".hidden/private.go": b"hidden source\n",
                "excluded/skip.go": b"excluded source\n",
                "alpha/.hidden.go": b"hidden file\n",
                "alpha/omit.go": b"excluded file\n",
            }
            for name, content in sources.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            artifacts = []
            traversals = []
            for reverse in (False, True):
                visited = []

                def enumerate_tree(startpath, topdown=True):
                    self.assertTrue(topdown)

                    def visit(path):
                        visited.append(path.relative_to(root).as_posix())
                        entries = sorted(path.iterdir(), reverse=reverse)
                        dirs = [entry.name for entry in entries if entry.is_dir()]
                        files = [entry.name for entry in entries if entry.is_file()]
                        yield str(path), dirs, files
                        # Match os.walk's in-place recursion-pruning contract.
                        for name in dirs:
                            yield from visit(path / name)
                    yield from visit(Path(startpath))

                tree = base / "tree.txt"
                legacy = base / "legacy.txt"
                combined = base / "combined.txt"
                with patch.object(directory_tree.os, "walk", enumerate_tree):
                    directory_tree.save_dir_tree_to_file(
                        str(root), str(tree), packages=["demo"],
                        exclude=["excluded", "omit.go"],
                    )
                directory_tree.replace_suffix_in_file(str(tree), str(legacy))
                directory_tree.append_files_with_blurb(
                    str(tree), str(legacy), str(combined), "Source and legacy views",
                )
                artifacts.append(tuple(path.read_bytes() for path in (tree, legacy, combined)))
                traversals.append(visited)
            self.assertEqual(artifacts[0], artifacts[1])
            self.assertEqual(traversals, [[".", "alpha", "alpha/deep", "beta"]] * 2)
            text = artifacts[0][0].decode("utf-8")
            self.assertLess(text.index("a.go"), text.index("z.go"))
            for absent in (".hidden", "excluded", "omit.go", "private.go", "skip.go"):
                self.assertNotIn(absent, text)
            for name, content in sources.items():
                self.assertEqual((root / name).read_bytes(), content)

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


if __name__ == "__main__":
    unittest.main()
