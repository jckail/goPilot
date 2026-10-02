"""Offline regression checks for the Go analysis-context consolidator."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


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
                path.write_text(source)
            packages, outputs = getter.consolidate_go_files(directory)
            return dict(packages), {Path(p).name: Path(p).read_text() for p in outputs}

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
