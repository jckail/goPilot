"""Run only selected source AST, never import helpers or call a provider."""
import ast
import pathlib
import types
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "goHelpers" / "main.py"


class RuntimeConfigTests(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse(SOURCE.read_text())
        self.function = next(node for node in self.tree.body
                             if isinstance(node, ast.FunctionDef)
                             and node.name == "require_runtime_key")
        self.namespace = {}
        exec(compile(ast.Module(body=[self.function], type_ignores=[]),
                     str(SOURCE), "exec"), self.namespace)

    def test_missing_or_blank_key_rejected_without_echoing_value(self):
        for environment in [{}, {"OPENAI_API_KEY": ""},
                            {"OPENAI_API_KEY": " \t\n"}]:
            with self.subTest(environment=bool(environment)):
                with self.assertRaisesRegex(ValueError, "runtime environment"):
                    self.namespace["require_runtime_key"](environment)

    def test_configured_key_is_not_returned_or_changed(self):
        environment = {"OPENAI_API_KEY": "synthetic-placeholder"}
        self.assertIsNone(self.namespace["require_runtime_key"](environment))
        self.assertEqual(environment, {"OPENAI_API_KEY": "synthetic-placeholder"})

    def test_real_startup_guard_exits_before_context_or_provider_work(self):
        main = next(node for node in self.tree.body if isinstance(node, ast.If)
                    and isinstance(node.test, ast.Compare)
                    and isinstance(node.test.left, ast.Name)
                    and node.test.left.id == "__name__")
        guard_index = next(i for i, node in enumerate(main.body)
                           if isinstance(node, ast.Try)
                           and any(isinstance(call, ast.Call)
                                   and isinstance(call.func, ast.Name)
                                   and call.func.id == "require_runtime_key"
                                   for call in ast.walk(node)))
        prefix = main.body[:guard_index + 1]
        calls = [node for statement in prefix for node in ast.walk(statement)
                 if isinstance(node, ast.Call)]
        self.assertFalse(any(isinstance(call.func, ast.Attribute)
                             and isinstance(call.func.value, ast.Name)
                             and call.func.value.id in {"walkIt", "getter", "addGo"}
                             for call in calls))
        messages = []
        runtime = dict(self.namespace,
                       sys=types.SimpleNamespace(argv=["main.py", ".", ".", "false", "false"],
                                                 exit=lambda code: (_ for _ in ()).throw(SystemExit(code))),
                       os=types.SimpleNamespace(environ={}),
                       logger=types.SimpleNamespace(error=lambda *args: messages.append(args)))
        with self.assertRaises(SystemExit) as exited:
            exec(compile(ast.Module(body=prefix, type_ignores=[]),
                         str(SOURCE), "exec"), runtime)
        self.assertEqual(exited.exception.code, 1)
        self.assertTrue(messages)
        self.assertIn("OPENAI_API_KEY", str(messages))

    def test_no_credential_shaped_literal_remains(self):
        self.assertFalse(any(isinstance(node, ast.Constant)
                             and isinstance(node.value, str)
                             and node.value.startswith("sk-")
                             for node in ast.walk(self.tree)))


if __name__ == "__main__":
    unittest.main()
