# Copyright (c) 2026, ALYF GmbH and Contributors
# See LICENCE

"""Checks for the one piece of the migrator that rewrites a file it doesn't own.

Run with ``pytest tests/`` or plain ``python tests/test_hooks_editor.py``.

Every case asserts the result still parses: corrupting a target's hooks.py is worse
than refusing to touch it, and the failure is otherwise silent.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from erpnext_druckformate_migrator.hooks_editor import add_hook  # noqa: E402

TARGET = "my_app.print_format_sources.print_formats.sync_print_formats"


def _run(source: str, hooks=("after_migrate", "after_install")):
	"""Apply ``add_hook`` per hook name, as the CLI does. Returns (text, results)."""
	with TemporaryDirectory() as tmp:
		path = Path(tmp) / "hooks.py"
		path.write_text(source, encoding="utf-8")
		results = [add_hook(path, name, TARGET) for name in hooks]
		return path.read_text(encoding="utf-8"), results


def _hook_value(text: str, name: str):
	"""Read a top-level assignment back out of the rewritten source."""
	tree = ast.parse(text)  # also asserts the result is still valid Python
	for node in tree.body:
		if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == name:
			return ast.literal_eval(node.value)
	return None


def test_multiline_list_is_not_spliced_into():
	# Regression: text anchoring inserted `after_install` inside the list.
	text, _ = _run('app_name = "my_app"\n\nafter_migrate = [\n\t"my_app.tasks.rebuild",\n]\n')
	assert _hook_value(text, "after_migrate") == ["my_app.tasks.rebuild", TARGET]
	assert _hook_value(text, "after_install") == [TARGET]


def test_string_form_is_expanded_to_list():
	text, _ = _run('after_install = "my_app.install.after_install"\n')
	assert _hook_value(text, "after_install") == ["my_app.install.after_install", TARGET]
	assert _hook_value(text, "after_migrate") == [TARGET]


def test_single_line_list_is_appended_to():
	text, _ = _run('after_migrate = ["a.b"]\n')
	assert _hook_value(text, "after_migrate") == ["a.b", TARGET]


def test_empty_file():
	text, _ = _run("")
	assert _hook_value(text, "after_migrate") == [TARGET]
	assert _hook_value(text, "after_install") == [TARGET]


def test_no_trailing_newline_does_not_glue_lines():
	text, _ = _run('app_name = "my_app"')  # no "\n" at EOF
	assert _hook_value(text, "after_migrate") == [TARGET]
	assert _hook_value(text, "after_install") == [TARGET]


def test_rerun_is_idempotent():
	once, _ = _run('app_name = "my_app"\n')
	with TemporaryDirectory() as tmp:
		path = Path(tmp) / "hooks.py"
		path.write_text(once, encoding="utf-8")
		results = [add_hook(path, n, TARGET) for n in ("after_migrate", "after_install")]
		assert all(r.noop and not r.changed for r in results)
		assert path.read_text(encoding="utf-8") == once


def test_surrounding_code_survives():
	src = (
		'app_name = "my_app"\n'
		"\n"
		"# a comment we must not eat\n"
		'doc_events = {"Sales Invoice": {"on_submit": "my_app.x"}}\n'
		'after_migrate = ["a.b"]\n'
		"\n"
		"def helper():\n"
		"\treturn 1\n"
	)
	text, _ = _run(src)
	assert "# a comment we must not eat" in text
	assert "def helper():" in text
	assert _hook_value(text, "doc_events") == {"Sales Invoice": {"on_submit": "my_app.x"}}


def test_refuses_non_literal_value_without_writing():
	src = "after_migrate = get_hooks()\n"
	text, results = _run(src, hooks=("after_migrate",))
	assert text == src, "must not rewrite a hook it cannot read"
	assert not results[0].changed and not results[0].noop, "must report a refusal"


def test_refuses_file_with_syntax_error_without_writing():
	src = "after_migrate = [\n"
	text, results = _run(src, hooks=("after_migrate",))
	assert text == src
	assert not results[0].changed and not results[0].noop


if __name__ == "__main__":
	for name, fn in sorted(globals().items()):
		if name.startswith("test_"):
			fn()
			print(f"ok  {name}")
	print("\nall hooks_editor checks passed")
