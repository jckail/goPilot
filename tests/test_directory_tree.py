"""Actual-module checks for legacy tree file-suffix conversion."""

import importlib.util
import ast
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
    def test_every_generated_producer_explicitly_selects_generated_conversion(self):
        helper = Path(__file__).resolve().parents[1] / "goHelpers"
        for filename in ["directoryTree.py", "exportContext.py", "main.py"]:
            with self.subTest(filename=filename):
                tree = ast.parse((helper / filename).read_text(encoding="utf-8"))
                calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                         and ((isinstance(node.func, ast.Name) and node.func.id == "replace_suffix_in_file")
                              or (isinstance(node.func, ast.Attribute) and node.func.attr == "replace_suffix_in_file"))]
                self.assertEqual(len(calls), 1)
                self.assertTrue(any(keyword.arg == "generated_tree" and isinstance(keyword.value, ast.Constant)
                                    and keyword.value.value is True for keyword in calls[0].keywords))

    def test_exact_hierarchy_with_shared_directory_and_file_siblings(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "demo"
            (root / "alpha" / "deep").mkdir(parents=True)
            (root / "beta").mkdir()
            for name in ["main.go", "alpha/a.go", "alpha/deep/deep.go"]:
                (root / name).write_bytes(b"preserved\n")
            output = base / "tree.txt"
            directory_tree.save_dir_tree_to_file(str(root), str(output))
            self.assertEqual(output.read_text(encoding="utf-8"),
                             "This go project is called: demo's here is it's current directory tree.\n"
                             "demo/\n"
                             "├── alpha/\n"
                             "│   ├── deep/\n"
                             "│   │   └── deep.go\n"
                             "│   └── a.go\n"
                             "├── beta/\n"
                             "└── main.go\n")
            for name in ["main.go", "alpha/a.go", "alpha/deep/deep.go"]:
                self.assertEqual((root / name).read_bytes(), b"preserved\n")

    def test_last_directory_uses_spaces_for_descendants(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "demo"
            (root / "alpha" / "deep").mkdir(parents=True)
            (root / "alpha" / "deep" / "last.go").write_bytes(b"source")
            output = base / "tree.txt"
            directory_tree.save_dir_tree_to_file(str(root), str(output))
            self.assertEqual(output.read_text().splitlines()[2:],
                             ["└── alpha/", "    └── deep/", "        └── last.go"])

    def test_directory_symlink_is_explicit_leaf_and_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "demo"
            root.mkdir()
            outside = base / "target"
            outside.mkdir()
            (outside / "private.go").write_bytes(b"outside unchanged")
            (root / "alias.go").symlink_to(outside, target_is_directory=True)
            (root / "last.go").write_bytes(b"inside unchanged")
            output = base / "tree.txt"
            directory_tree.save_dir_tree_to_file(str(root), str(output))
            self.assertEqual(output.read_text().splitlines()[2:],
                             ["├── alias.go/ [directory symlink; not followed]", "└── last.go"])
            self.assertEqual((outside / "private.go").read_bytes(), b"outside unchanged")
            self.assertTrue((root / "alias.go").is_symlink())

    def test_filesystem_anchor_is_not_empty_or_double_slash(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "tree.txt"

            def walk(root, topdown=True):
                self.assertEqual(root, "/")
                yield "/", [], ["root.go"]

            with patch.object(directory_tree.os, "walk", walk):
                directory_tree.save_dir_tree_to_file("/", str(output))
            self.assertEqual(output.read_text().splitlines()[1:], ["/", "└── root.go"])

    def test_escaped_labels_cannot_fabricate_rows_or_lose_unicode(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "demo\n\\root"
            root.mkdir()
            names = ["café space.go", "actual\n├── fake.go", "literal\\n.go", "tab\t.go", "bad\udcff.go"]
            for name in names:
                (root / name).write_bytes(b"source")
            output = base / "tree.txt"
            converted = base / "converted.txt"
            directory_tree.save_dir_tree_to_file(str(root), str(output), packages=["pkg\nname"])
            directory_tree.replace_suffix_in_file(str(output), str(converted), generated_tree=True)
            lines = output.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 4 + len(names))
            self.assertIn(r"demo\x0a\\root/", lines)
            for escaped in [r"actual\x0a├── fake.go", r"literal\\n.go", r"tab\x09.go", r"bad\udcff.go", "café space.go"]:
                self.assertEqual(sum(line.endswith(escaped) for line in lines), 1)
                self.assertIn(escaped[:-3] + "_go.txt", converted.read_text(encoding="utf-8"))
            for name in names:
                self.assertEqual((root / name).read_bytes(), b"source")

    def test_strict_inventory_failure_preserves_previous_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "tree.txt"
            output.write_bytes(b"previous tree")

            def failing_walk(root, topdown=True, onerror=None):
                yield root, [], ["seen.go"]
                onerror(PermissionError("synthetic traversal refusal"))

            with patch.object(directory_tree.os, "walk", failing_walk):
                with self.assertRaisesRegex(PermissionError, "traversal refusal"):
                    directory_tree.save_dir_tree_to_file(directory, str(output), strict_walk=True)
            self.assertEqual(output.read_bytes(), b"previous tree")

    def test_generated_converter_supports_root_and_ancestor_space_units(self):
        before = ("Header café.go\r\nroot.go/\r\n├── root.go\r\n"
                  "└── dir.go/\n    ├── child.go\r\n    │   └── deep.go\n"
                  "    └── alias.go/ [directory symlink; not followed]\n")
        expected = before.replace("├── root.go", "├── root_go.txt").replace("child.go", "child_go.txt").replace("deep.go", "deep_go.txt")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            output = Path(directory) / "output"
            source.write_bytes(before.encode("utf-8"))
            directory_tree.replace_suffix_in_file(str(source), str(output), generated_tree=True)
            self.assertEqual(output.read_bytes(), expected.encode("utf-8"))
            self.assertEqual(source.read_bytes(), before.encode("utf-8"))

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
                directory_tree.replace_suffix_in_file(str(tree), str(legacy), generated_tree=True)
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
            directory_tree.replace_suffix_in_file(str(source), str(output), generated_tree=True)
            actual = output.read_text(encoding="utf-8")
            self.assertIn("called: project.go's", actual)
            self.assertIn("Go Packages are: pkg.go\n", actual)
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
