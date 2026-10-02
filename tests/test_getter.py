"""Offline regression checks for the Go analysis-context consolidator."""

import ast
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "getter", Path(__file__).resolve().parents[1] / "goHelpers" / "getter.py"
)
getter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(getter)


class ConsolidationTests(unittest.TestCase):
    def consolidate(self, files):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, source in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding="utf-8")
            packages, outputs = getter.consolidate_go_files(directory)
            for name, source in files.items():
                self.assertEqual((root / name).read_bytes(), source.encode("utf-8"))
            return dict(packages), {Path(p).name: Path(p).read_text(encoding="utf-8") for p in outputs}

    def test_source_paths_disambiguate_nested_names_in_map_and_markers(self):
        packages, outputs = self.consolidate({
            "root.go": "package demo\nfunc Root() {}\n",
            "alpha/shared.go": "package demo\nfunc Alpha() {}\n",
            "café space/shared.go": "package demo\nfunc Unicode() {}\n",
            "café space/shared_test.go": "package demo\nfunc Excluded() {}\n",
        })
        paths = ["root.go", "alpha/shared.go", "café space/shared.go"]
        self.assertEqual(packages, {"demo": paths})
        for path in paths:
            self.assertEqual(outputs["demo_go.txt"].count("// This is the start of " + path), 1)
            self.assertEqual(outputs["demo_go.txt"].count("// This is the end of " + path), 1)
        self.assertNotIn("Excluded", outputs["demo_go.txt"])

    def test_live_main_map_writer_uses_actual_output_names_and_utf8(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / "goHelpers" / "main.py").read_text(encoding="utf-8"))
        blocks = [node for node in ast.walk(tree) if isinstance(node, ast.With)
                  and any(isinstance(item.context_expr, ast.Call)
                          and isinstance(item.context_expr.func, ast.Name)
                          and item.context_expr.func.id == "open"
                          and item.context_expr.args
                          and isinstance(item.context_expr.args[0], ast.Name)
                          and item.context_expr.args[0].id == "package_map_context"
                          for item in node.items)]
        self.assertEqual(len(blocks), 1)
        module = ast.fix_missing_locations(ast.Module(body=blocks, type_ignores=[]))
        builtin_open = open

        def ascii_default_open(*args, **kwargs):
            if "encoding" not in kwargs:
                kwargs["encoding"] = "ascii"
            return builtin_open(*args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "café space" / "shared.go"
            source.parent.mkdir()
            original = "package demo\nfunc Café() {}\n".encode("utf-8")
            source.write_bytes(original)
            packages, outputs = getter.consolidate_go_files(directory)
            context = root / "package_map_context.txt"
            exec(compile(module, "main-map-block", "exec"), {
                "getter": getter, "open": ascii_default_open,
                "package_map_context": str(context), "package_map": packages, "files": outputs,
            })
            self.assertEqual(context.read_text(encoding="utf-8"),
                             "'demo_go.txt' contains ['café space/shared.go']\n")
            self.assertTrue((root / "demo_go.txt").exists())
            self.assertEqual([Path(p).name for p in outputs], ["demo_go.txt"])
            self.assertEqual(source.read_bytes(), original)

    def test_failed_context_writes_remain_inventory_without_false_references(self):
        builtin_open = open
        for refused in ({"demo_go.txt"}, {"demo_go.txt", "other_go.txt"}):
            with self.subTest(refused=refused), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                sources = {"a.go": "package demo\nfunc A() {}\n",
                           "b.go": "package other\nfunc B() {}\n"}
                for name, source in sources.items():
                    (root / name).write_text(source, encoding="utf-8")

                def refuse_output(path, mode="r", *args, **kwargs):
                    if mode == "w" and Path(path).name in refused:
                        raise OSError("synthetic output refusal")
                    return builtin_open(path, mode, *args, **kwargs)

                with patch.object(getter, "open", refuse_output, create=True):
                    packages, outputs = getter.consolidate_go_files(directory)
                text = getter.format_package_map(packages, outputs)
                self.assertEqual(dict(packages), {"demo": ["a.go"], "other": ["b.go"]})
                for package, paths in packages.items():
                    name = package + "_go.txt"
                    if name in refused:
                        self.assertFalse((root / name).exists())
                        self.assertNotIn(name, text)
                        self.assertIn(f"'{package}': context not generated; sources {paths}", text)
                    else:
                        self.assertTrue((root / name).exists())
                        self.assertIn(f"'{name}' contains {paths}", text)
                for name, source in sources.items():
                    self.assertEqual((root / name).read_bytes(), source.encode("utf-8"))

    def test_map_formatter_is_pure_and_tree_blurb_describes_aggregation(self):
        packages = {"demo": ["root.go", "nested/shared.go"], "other": ["other.go"]}
        original = {name: list(paths) for name, paths in packages.items()}
        self.assertEqual(getter.format_package_map(packages, ["/tmp/demo_go.txt", "/tmp/other_go.txt"]),
                         "'demo_go.txt' contains ['root.go', 'nested/shared.go']\n"
                         "'other_go.txt' contains ['other.go']\n")
        self.assertEqual(packages, original)
        self.assertEqual(getter.format_package_map({}, []), "")
        tree = ast.parse((Path(__file__).resolve().parents[1] / "goHelpers" / "main.py").read_text(encoding="utf-8"))
        assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == "blurb_text" for target in node.targets)]
        self.assertEqual(len(assignments), 1)
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=assignments, type_ignores=[])),
                     "main-blurb", "exec"), namespace)
        blurb = namespace["blurb_text"]
        self.assertIn("package_map_context.txt", blurb)
        self.assertIn("root-relative", blurb)
        self.assertIn("per-package", blurb)
        self.assertIn("legacy", blurb)
        self.assertNotIn("one to one", blurb)
        self.assertNotIn("identical", blurb)

    def test_context_is_reproducible_across_directory_enumeration(self):
        sources = {
            "b.go": "package demo\nfunc B() {}\n",
            "a.go": "package demo\nfunc A() {}\n",
            "alpha/second.go": "package demo\nfunc AlphaSecond() {}\n",
            "alpha/first.go": "package demo\nfunc AlphaFirst() {}\n",
            "alpha/other.go": "package alpha\nfunc Other() {}\n",
            "beta/shared.go": "package demo\nfunc Beta() {}\n",
            "beta/z.go": "package zeta\nfunc Z() {}\n",
            "skip_test.go": "package demo\nfunc Excluded() {}\n",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, source in sources.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding="utf-8")

            def controlled_walk(path, reverse):
                # Like os.walk(topdown=True), descent honors caller changes to dirs.
                dirs = sorted((p.name for p in Path(path).iterdir() if p.is_dir()),
                              reverse=reverse)
                files = sorted((p.name for p in Path(path).iterdir() if p.is_file()),
                               reverse=reverse)
                yield str(path), dirs, files
                for dirname in dirs:
                    yield from controlled_walk(Path(path) / dirname, reverse)

            snapshots = []
            for reverse in (False, True):
                with patch.object(getter.os, "walk", side_effect=lambda path: controlled_walk(path, reverse)):
                    packages, outputs = getter.consolidate_go_files(directory)
                snapshots.append((list(packages.items()),
                                  [Path(p).name for p in outputs],
                                  {Path(p).name: Path(p).read_bytes() for p in outputs}))
                for name, source in sources.items():
                    self.assertEqual((root / name).read_bytes(), source.encode("utf-8"))
            self.assertEqual(snapshots[0], snapshots[1])
            packages, outputs, contents = snapshots[0]
            self.assertEqual(packages, [
                ("demo", ["a.go", "b.go", "alpha/first.go", "alpha/second.go", "beta/shared.go"]),
                ("alpha", ["alpha/other.go"]), ("zeta", ["beta/z.go"]),
            ])
            self.assertEqual(outputs, ["demo_go.txt", "alpha_go.txt", "zeta_go.txt"])
            self.assertNotIn(b"Excluded", contents["demo_go.txt"])
            self.assertEqual(contents["demo_go.txt"].count(b"func "), 5)

    def test_initial_bom_preserves_file_and_import_identity(self):
        packages, outputs = self.consolidate({
            "bom.go": '\ufeff// license\r\n\r\npackage demo\r\nimport f "fmt"\r\nfunc Café() {}\r\n',
            "plain.go": 'package demo\nimport f "fmt"\nfunc Plain() {}\n',
        })
        self.assertEqual(set(packages["demo"]), {"bom.go", "plain.go"})
        text = outputs["demo_go.txt"]
        self.assertIn("// license", text)
        self.assertIn("func Café()", text)
        self.assertIn("func Plain()", text)
        self.assertEqual(text.count('f "fmt"'), 1)
        self.assertNotIn("\ufeff", text)

    def test_header_reader_ignores_exactly_one_initial_bom(self):
        package, imports, body = getter._extract_go_header('\ufeffpackage demo\nimport "fmt"\nfunc One() {}\n')
        self.assertEqual((package, imports), ("demo", {'"fmt"'}))
        self.assertIn("func One()", body)
        for source in ['\ufeff\ufeffpackage demo\n', '\n\ufeffpackage demo\n']:
            with self.subTest(source=source):
                package, _, _ = getter._extract_go_header(source)
                self.assertIsNone(package)

    def test_interior_bom_source_text_is_preserved(self):
        body = 'const raw = `inside\ufeffliteral`\n// comment\ufefftext\nfunc Keep() {}\n'
        _, outputs = self.consolidate({"one.go": '\ufeffpackage demo\n' + body})
        self.assertIn(body, outputs["demo_go.txt"])

    def test_unicode_io_does_not_use_ascii_locale_default(self):
        native_open = open

        def ascii_default_open(file, mode="r", *args, **kwargs):
            if "b" not in mode and not kwargs.get("encoding"):
                kwargs["encoding"] = "ascii"
            return native_open(file, mode, *args, **kwargs)

        # Emulate an ASCII default only at the helper's file-I/O boundary.
        # Real UTF-8 temporary files still exercise decoding and output encoding.
        with patch.object(getter, "open", ascii_default_open, create=True):
            packages, outputs = self.consolidate({
                "unicode.go": 'package demo\n// résumé\nfunc Café() {}\n',
            })
        self.assertEqual(packages, {"demo": ["unicode.go"]})
        self.assertIn("// résumé", outputs["demo_go.txt"])
        self.assertIn("func Café()", outputs["demo_go.txt"])

    def test_single_imports_deduplicate_after_leading_blank_lines(self):
        _, outputs = self.consolidate({
            "one.go": '\n\npackage main\nimport "fmt"\nfunc one() {}\n',
            "two.go": 'package main\nimport "fmt"\nfunc two() {}\n',
        })
        text = outputs["main_go.txt"]
        self.assertEqual(text.count('"fmt"'), 1)
        self.assertIn("func one()", text)
        self.assertIn("func two()", text)

    def test_grouped_and_single_aliases_remain_complete_specs(self):
        _, outputs = self.consolidate({
            "one.go": 'package demo\nimport (\n f "fmt"\n _ "net/http"\n . "strings"\n)\nfunc one() {}\n',
            "two.go": 'package demo\nimport f\t"fmt"\nimport _ "net/http"\nfunc two() {}\n',
        })
        text = outputs["demo_go.txt"]
        self.assertIn('f "fmt"', text)
        self.assertIn('_ "net/http"', text)
        self.assertIn('. "strings"', text)
        self.assertEqual(text.count('"fmt"'), 1)
        self.assertEqual(text.count('"net/http"'), 1)

    def test_different_aliases_are_not_merged(self):
        _, outputs = self.consolidate({
            "one.go": 'package demo\nimport first "fmt"\n',
            "two.go": 'package demo\nimport second "fmt"\n',
        })
        text = outputs["demo_go.txt"]
        self.assertIn('first "fmt"', text)
        self.assertIn('second "fmt"', text)

    def test_comments_raw_paths_and_same_line_group_specs(self):
        _, outputs = self.consolidate({
            "one.go": '// license\npackage demo;\nimport (f /* alias */ `fmt`; "os")\nfunc one() {}\n',
            "two.go": 'package demo\nimport "os" // shared\n',
        })
        text = outputs["demo_go.txt"]
        self.assertTrue(text.startswith("package demo\n"))
        self.assertIn('f "fmt"', text)
        self.assertEqual(text.count('"os"'), 1)
        self.assertIn("// license", text)

    def test_source_strings_and_comments_are_not_import_declarations(self):
        source = 'package demo\nimport "fmt"\nconst sample = `\nimport "fake"\npackage imaginary\n`\n/*\nimport "comment"\n*/\n'
        _, outputs = self.consolidate({"one.go": source})
        text = outputs["demo_go.txt"]
        self.assertIn('const sample = `\nimport "fake"\npackage imaginary\n`', text)
        self.assertIn('/*\nimport "comment"\n*/', text)
        header = text.split("// This is the start", 1)[0]
        self.assertNotIn('"fake"', header)
        self.assertNotIn('"comment"', header)

    def test_group_import_text_inside_body_is_preserved(self):
        body = 'func example() string { return `\nimport (\n"fake"\n)\n` }\n'
        _, outputs = self.consolidate({
            "one.go": 'package demo\nimport "fmt"\n' + body,
        })
        text = outputs["demo_go.txt"]
        self.assertIn(body, text)
        self.assertNotIn('"fake"', text.split("// This is the start", 1)[0])

    def test_only_go_test_suffix_is_excluded(self):
        packages, outputs = self.consolidate({
            "helper_testing.go": 'package demo\nfunc helper() {}\n',
            "helper_test.go": 'package demo\nfunc TestHelper() {}\n',
        })
        self.assertEqual(packages, {"demo": ["helper_testing.go"]})
        self.assertIn("func helper", outputs["demo_go.txt"])
        self.assertNotIn("TestHelper", outputs["demo_go.txt"])

    def test_no_imports_produces_no_empty_import_block(self):
        _, outputs = self.consolidate({"one.go": 'package demo\nfunc one() {}\n'})
        self.assertNotIn("import (", outputs["demo_go.txt"])

    def test_crlf_and_tabbed_alias_with_trailing_comments(self):
        _, outputs = self.consolidate({
            "one.go": '\r\npackage demo\r\nimport f\t"fmt" // note\r\nfunc one() {}\r\n',
            "two.go": 'package demo\nimport ( f "fmt" /* note */ )\n',
        })
        text = outputs["demo_go.txt"]
        self.assertEqual(text.count('"fmt"'), 1)
        self.assertIn('f "fmt"', text)
        header = text.split("// This is the start", 1)[0]
        self.assertNotIn("note", header)

    def test_equivalent_quoted_raw_and_escaped_paths_deduplicate(self):
        _, outputs = self.consolidate({
            "one.go": 'package demo\nimport `fmt`\nimport f `fmt`\n',
            "two.go": 'package demo\nimport "fmt"\nimport f "f\\x6dt"\n',
        })
        text = outputs["demo_go.txt"]
        header = text.split("// This is the start", 1)[0]
        self.assertEqual(header.count('"fmt"'), 2)
        self.assertIn('\n"fmt"\n', header)
        self.assertIn('\nf "fmt"\n', header)
        self.assertNotIn('`fmt`', text)
        self.assertNotIn('f\\x6dt', text)

    def test_packages_remain_separate_and_test_files_are_excluded(self):
        packages, outputs = self.consolidate({
            "main.go": 'package main\nimport "fmt"\nfunc main() {}\n',
            "main_test.go": 'package main\nimport "testing"\nfunc TestMain() {}\n',
            "lib/helper.go": 'package helper\nimport "strings"\nfunc Help() {}\n',
        })
        self.assertEqual(packages, {"main": ["main.go"], "helper": ["lib/helper.go"]})
        self.assertEqual(set(outputs), {"main_go.txt", "helper_go.txt"})
        self.assertNotIn("TestMain", outputs["main_go.txt"])
        self.assertNotIn('"testing"', outputs["main_go.txt"])
        self.assertNotIn("func Help", outputs["main_go.txt"])


if __name__ == "__main__":
    unittest.main()
