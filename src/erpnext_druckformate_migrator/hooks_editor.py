# Copyright (c) 2026, ALYF GmbH and Contributors
# See LICENCE

"""Conservative AST-aware edits to a target Frappe app's ``hooks.py``.

Adds an entry to a hook variable (``after_migrate`` or ``after_install``).
Supports the cases that actually appear in the wild:

  hook_name = "single.fn"                    -> rewrite as list, append ours
  hook_name = ["fn1", "fn2"]                 -> append ours
  hook_name = [\\n    "fn1",\\n    "fn2",\\n]  -> append ours (multi-line preserved)
  (missing)                                  -> insert `hook_name = ["ours"]`
  hook_name = some_func()                    -> refuse (non-literal RHS)
  hook_name already includes our target      -> noop

Philosophy: AST locates the node and reads its current value via ``literal_eval``;
text splicing applies the new assignment so surrounding code/comments are untouched.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EditResult:
	"""One file edit. ``noop`` means the desired state was already present."""

	path: Path
	changed: bool
	noop: bool
	message: str


def add_hook(hooks_path: Path, hook_name: str, target: str) -> EditResult:
	"""Ensure ``hook_name`` in ``hooks_path`` includes ``target``."""
	if not hooks_path.is_file():
		raise FileNotFoundError(f"hooks.py not found: {hooks_path}")

	text = hooks_path.read_text(encoding="utf-8")
	try:
		tree = ast.parse(text)
	except SyntaxError as e:
		return EditResult(
			hooks_path, changed=False, noop=False,
			message=f"refusing to edit: hooks.py has a syntax error ({e})",
		)

	existing = _find_assignment(tree, hook_name)

	if existing is None:
		new_line = _format_list_assignment(hook_name, [target])
		new_text = _insert_new_line(text, tree, new_line)
		hooks_path.write_text(new_text, encoding="utf-8")
		return EditResult(
			hooks_path, changed=True, noop=False,
			message=f"added new `{hook_name}` -> {target!r}",
		)

	try:
		current_value = ast.literal_eval(existing.value)
	except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
		return EditResult(
			hooks_path, changed=False, noop=False,
			message=(
				f"refusing to edit: `{hook_name}` in hooks.py has a non-literal value; "
				f"add {target!r} to it manually"
			),
		)

	if isinstance(current_value, str):
		current_list = [current_value]
	elif isinstance(current_value, list) and all(isinstance(x, str) for x in current_value):
		current_list = list(current_value)
	else:
		return EditResult(
			hooks_path, changed=False, noop=False,
			message=(
				f"refusing to edit: `{hook_name}` is not a string or list of strings; "
				f"add {target!r} to it manually"
			),
		)

	if target in current_list:
		return EditResult(
			hooks_path, changed=False, noop=True,
			message=f"`{hook_name}` already includes {target!r}",
		)

	new_list = current_list + [target]
	new_assignment = _format_list_assignment(hook_name, new_list)
	new_text = _splice(text, existing, new_assignment)
	hooks_path.write_text(new_text, encoding="utf-8")
	verb = "expanded" if isinstance(current_value, str) else "appended to"
	return EditResult(
		hooks_path, changed=True, noop=False,
		message=f"{verb} `{hook_name}`: added {target!r}",
	)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _find_assignment(tree: ast.Module, name: str) -> ast.Assign | None:
	"""Return the top-level ``Assign`` whose single target is ``name``, or ``None``."""
	for node in tree.body:
		if (
			isinstance(node, ast.Assign)
			and len(node.targets) == 1
			and isinstance(node.targets[0], ast.Name)
			and node.targets[0].id == name
		):
			return node
	return None


def _format_list_assignment(name: str, items: list[str]) -> str:
	"""Pick a stable single-line form by default; switch to multi-line for long lists."""
	single = f"{name} = [{', '.join(_q(x) for x in items)}]"
	if len(single) <= 100:
		return single
	body = "\n".join(f"\t{_q(x)}," for x in items)
	return f"{name} = [\n{body}\n]"


def _q(s: str) -> str:
	"""Render a string as a Python double-quoted literal."""
	escaped = s.replace("\\", "\\\\").replace('"', '\\"')
	return f'"{escaped}"'


def _splice(text: str, node: ast.Assign, replacement: str) -> str:
	"""Replace lines ``[node.lineno, node.end_lineno]`` with ``replacement``."""
	lines = text.splitlines(keepends=True)
	# AST line numbers are 1-indexed.
	before = "".join(lines[: node.lineno - 1])
	after = "".join(lines[node.end_lineno :])
	# Preserve a trailing newline if the original had one.
	suffix = "\n" if not replacement.endswith("\n") else ""
	return before + replacement + suffix + after


def _insert_new_line(text: str, tree: ast.Module, line: str) -> str:
	"""Insert ``line`` after an existing hook-style assignment, or at EOF.

	The anchor comes from the AST, not from matching text: a multi-line value
	(``after_migrate = [\\n ... \\n]``) must be stepped over as a whole, or the
	new assignment lands inside the list and breaks the file.
	"""
	for anchor in ("after_install", "after_migrate", "app_name"):
		node = _find_assignment(tree, anchor)
		if node is None:
			continue
		lines = text.splitlines(keepends=True)
		if lines and not lines[-1].endswith("\n"):
			lines[-1] += "\n"  # else an anchor at EOF glues to the new line
		# end_lineno is 1-indexed and inclusive, so it already points past the node.
		lines.insert(node.end_lineno, line + "\n")
		return "".join(lines)
	suffix = "" if text.endswith("\n") else "\n"
	return f"{text}{suffix}{line}\n"
