# Copyright (c) 2026, ALYF GmbH and Contributors
# See license.txt

"""Build **Print Format** docs from ``config.PRINT_FORMATS`` (+ templates, CSS) and sync on migrate."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .config import PRINT_FORMATS, SHARED_CSS

# Baseline for **Print Format** import; override per-format under ``fields`` only when you need to differ.
# Frappe's own ``doctype`` marker ("Print Format") is set explicitly at doc construction.
PRINT_FORMAT_DEFAULTS: dict[str, Any] = {
	"print_format_type": "Jinja",
	"disabled": 0,
	"standard": "Yes",
	"custom_format": 1,
	"align_labels_right": 0,
	"show_section_headings": 0,
	"line_breaks": 0,
	"absolute_value": 0,
	"font_size": 14,
	"page_number": "Hide",
	"font": None,
	"format_data": None,
	"print_format_builder": 0,
	"print_format_builder_beta": 0,
	"raw_printing": 0,
	"raw_commands": None,
	"default_print_language": None,
	"margin_top": 15.0,
	"margin_bottom": 15.0,
	"margin_left": 15.0,
	"margin_right": 15.0,
	"report": None,
	# Majority of current formats; sales-invoice variants override ``print_format_for`` / ``pdf_generator`` under ``fields``.
	"print_format_for": "DocType",
	"pdf_generator": "wkhtmltopdf",
}

# Anything in ``"fields"`` that isn't here raises during build (typo guard).
# = every defaulted field, plus ``module`` (allowed but not defaulted).
ALLOWED_FIELD_OVERRIDES = frozenset(PRINT_FORMAT_DEFAULTS) | {"module"}


def _load_text(path: Path) -> str:
	if not path.is_file():
		raise FileNotFoundError(path)
	return path.read_text(encoding="utf-8")


def build_print_format_docs(sources_root: Path) -> list[dict[str, Any]]:
	"""Return **Print Format** dicts ready for ``import_doc`` (no Frappe dependency)."""
	if not sources_root.is_dir():
		raise FileNotFoundError(f"print format sources not found: {sources_root}")

	docs: list[dict[str, Any]] = []
	for name, spec in PRINT_FORMATS.items():
		doc_type = spec.get("DocType")
		if not doc_type:
			raise ValueError(f"[{name}] missing DocType")
		template_rel = spec.get("template")
		if not template_rel:
			raise ValueError(f"[{name}] missing template")

		# Missing key -> shared default; ``None`` -> no CSS for this format.
		css_rel = spec.get("css", SHARED_CSS)
		css = _load_text(sources_root / css_rel) if css_rel else ""

		fields = spec.get("fields") or {}
		unknown = set(fields) - ALLOWED_FIELD_OVERRIDES
		if unknown:
			raise ValueError(f"[{name}] unknown field(s): {sorted(unknown)}")

		docs.append(
			{
				**PRINT_FORMAT_DEFAULTS,
				**fields,
				"doctype": "Print Format",
				"name": name,
				"doc_type": doc_type,
				"html": _load_text(sources_root / template_rel),
				"css": css,
			}
		)

	if not docs:
		raise ValueError("No print formats defined in config.PRINT_FORMATS")

	return docs


def _package_dir() -> Path:
	return Path(__file__).resolve().parent


def sync_print_formats() -> None:
	"""``after_migrate`` hook: export built docs to a temp JSON file and ``import_doc``."""
	import frappe
	from frappe.core.doctype.data_import.data_import import (
		import_doc as import_doc_from_path,
	)

	docs = build_print_format_docs(_package_dir())
	print(f"Syncing {len(docs)} print formats from sources...")
	frappe.logger().info("Syncing %s print formats from source", len(docs))

	tmp_path: str | None = None
	try:
		with NamedTemporaryFile(
			mode="w", suffix=".json", delete=False, encoding="utf-8"
		) as tmp:
			json.dump(docs, tmp, ensure_ascii=False)
			tmp.flush()
			tmp_path = tmp.name
		import_doc_from_path(tmp_path)
	finally:
		if tmp_path:
			Path(tmp_path).unlink(missing_ok=True)
