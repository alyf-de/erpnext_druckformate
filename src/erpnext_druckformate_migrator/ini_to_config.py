# Copyright (c) 2026, ALYF GmbH and Contributors
# See LICENCE

"""Convert an erpnext_druckformate-style ``config.ini`` into a Python ``config.py`` source string.

The output is a Pythonic ``PRINT_FORMATS`` mapping:

    PRINT_FORMATS = {
        "<Print Format Name>": {
            "DocType": "<DocType>",
            "template": "<filename>.jinja",
            "fields": {  # optional, only if INI provides non-default keys
                "module": "Stock",
                ...
            },
        },
        ...
    }

Every format shares the one compiled ``print_formats.css``. The generated builder
still honours a per-format ``css`` key, but that is a hand-edit escape hatch in the
target app: the INI has no say in it, since the migrator only copies the stylesheet
it compiled.

INI keys handled specially (not propagated into ``fields``):
- ``DocType`` -> top-level ``DocType``
- ``TemplateFile`` -> top-level ``template`` (filename only; the source's
  ``print_format/`` prefix is stripped)
- ``ScssFile`` and ``IsStandard`` (DEFAULT-only legacy keys) are ignored;
  the migrator compiles SCSS itself and the builder always writes
  ``standard = "No"``.

Any other INI key is treated as a Print Format field override and goes under ``fields``.
Empty values become ``None`` (clears the builder default).
"""

from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path
from typing import Any

# DEFAULT-only legacy keys from update.py-era configs; ignored by the new builder.
LEGACY_DEFAULT_KEYS = frozenset({"scssfile", "isstandard"})


def _coerce(raw: str) -> Any:
    """Empty INI value -> ``None`` (clears the builder default); otherwise the stripped string."""
    s = raw.strip()
    return None if s == "" else s


def _strip_template_prefix(template_file: str) -> str:
    """Strip the legacy ``print_format/`` prefix; the migrator copies templates flat."""
    return Path(template_file).name


def parse_ini(ini_path: Path) -> dict[str, dict[str, Any]]:
    """Parse a config.ini and return a normalized ``PRINT_FORMATS``-shaped dict.

    Validation:
    - At least one section.
    - Every section has a non-empty ``DocType`` and ``TemplateFile``.
    """
    parser = ConfigParser(interpolation=None)
    if not parser.read(ini_path, encoding="utf-8"):
        raise FileNotFoundError(f"Missing or empty {ini_path}")

    if not parser.sections():
        raise ValueError(f"{ini_path} has no [Section] entries")

    formats: dict[str, dict[str, Any]] = {}
    for section in parser.sections():
        items = dict(parser.items(section))

        # Drop legacy DEFAULT-inherited keys from per-section view.
        for key in LEGACY_DEFAULT_KEYS:
            items.pop(key, None)

        doc_type = items.pop("doctype", "").strip()
        if not doc_type:
            raise ValueError(f"[{section}] missing DocType")

        template_file = items.pop("templatefile", "").strip()
        if not template_file:
            raise ValueError(f"[{section}] missing TemplateFile")

        if "cssfile" in items:
            # Would emit a `css` reference to a file we never copy.
            raise ValueError(
                f"[{section}] CssFile is not supported: every format shares the CSS "
                f"compiled from print_style/*.scss. Set `css` by hand in the generated "
                f"config.py if you really need a per-format override."
            )

        spec: dict[str, Any] = {
            "DocType": doc_type,
            "template": _strip_template_prefix(template_file),
        }

        # Whatever remains is a Print Format field override.
        if items:
            spec["fields"] = {k: _coerce(v) for k, v in items.items()}

        formats[section] = spec

    return formats


def render_config_py(formats: dict[str, dict[str, Any]]) -> str:
    """Render ``PRINT_FORMATS`` as a Python source file string with stable indentation (tabs)."""
    lines: list[str] = [
        "# Copyright (c) 2026, ALYF GmbH and Contributors",
        "# See license.txt",
        "",
        '"""Source-of-truth mapping for **Print Format** docs synced by ``print_formats.py``.',
        "",
        "Per format:",
        "- key            **Print Format** name (shown in Desk)",
        "- ``DocType``    the DocType the format prints (required); maps to the Print Format ``doc_type`` field",
        "- ``template``   ``*.jinja`` filename next to this module (required)",
        "- ``css``        optional hand-added override: a filename next to this module, or",
        "                 ``None`` for no CSS. Omit to use ``SHARED_CSS`` (the default);",
        "                 if you add one, drop the file in this folder yourself.",
        "- ``fields``     optional dict of additional **Print Format** field overrides",
        "                 (e.g. ``module``, ``pdf_generator``, ``default_print_language``,",
        "                 margins, page number, ...)",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        'SHARED_CSS = "print_formats.css"',
        "",
        "PRINT_FORMATS: dict[str, dict] = {",
    ]
    for name, spec in formats.items():
        lines.append(f"\t{_py_str(name)}: {{")
        lines.append(f'\t\t"DocType": {_py_str(spec["DocType"])},')
        lines.append(f'\t\t"template": {_py_str(spec["template"])},')
        if fields := spec.get("fields"):
            lines.append("\t\t\"fields\": {")
            for fkey, fval in fields.items():
                lines.append(f"\t\t\t{_py_str(fkey)}: {_py_value(fval)},")
            lines.append("\t\t},")
        lines.append("\t},")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def _py_str(s: str) -> str:
    """Render a string as a Python literal, preferring double quotes."""
    if '"' in s and "'" not in s:
        return f"'{s}'"
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _py_value(v: Any) -> str:
    """Render an arbitrary value as a Python literal (None / str only in v1)."""
    if v is None:
        return "None"
    if isinstance(v, str):
        return _py_str(v)
    raise TypeError(f"unsupported value type for INI override: {type(v).__name__}")


def convert(ini_path: Path) -> str:
    """Parse + render in one shot."""
    return render_config_py(parse_ini(ini_path))
