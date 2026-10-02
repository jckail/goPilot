"""Offline regression checks for the Go analysis-context consolidator."""

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
                ("demo", ["a.go", "b.go", "first.go", "second.go", "shared.go"]),
                ("alpha", ["other.go"]), ("zeta", ["z.go"]),
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
        self.assertEqual(packages, {"main": ["main.go"], "helper": ["helper.go"]})
        self.assertEqual(set(outputs), {"main_go.txt", "helper_go.txt"})
        self.assertNotIn("TestMain", outputs["main_go.txt"])
        self.assertNotIn('"testing"', outputs["main_go.txt"])
        self.assertNotIn("func Help", outputs["main_go.txt"])


if __name__ == "__main__":
    unittest.main()
