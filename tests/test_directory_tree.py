"""Actual-module checks for legacy tree file-suffix conversion."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


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


if __name__ == "__main__":
    unittest.main()
