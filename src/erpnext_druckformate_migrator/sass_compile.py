# Copyright (c) 2026, ALYF GmbH and Contributors
# See LICENCE

"""Compile a SCSS file to expanded CSS via libsass.

We pick "expanded" output (not "compressed") because the produced ``print_formats.css``
is committed to the target app and humans will read it. The new builder doesn't care
about format — it just inlines the bytes into every Print Format's ``css`` field.
"""

from __future__ import annotations

from pathlib import Path

import sass


def compile_scss(scss_path: Path) -> str:
	"""Compile ``scss_path`` and return the resulting CSS as a string.

	Errors from libsass propagate as ``sass.CompileError`` with a useful message
	(file, line, column).
	"""
	if not scss_path.is_file():
		raise FileNotFoundError(f"SCSS source not found: {scss_path}")
	css = sass.compile(filename=str(scss_path), output_style="expanded")
	return _strip_leading_charset(css)


def _strip_leading_charset(css: str) -> str:
	"""Drop libsass's auto-prepended ``@charset "UTF-8";``.

	libsass adds this whenever the source contains non-ASCII bytes (e.g. German
	comments). The CSS is inlined into a **Print Format**'s ``css`` field — never
	served as a standalone stylesheet — so the directive is noise.
	"""
	prefix = '@charset "UTF-8";\n'
	if css.startswith(prefix):
		return css[len(prefix) :].lstrip("\n")
	return css
