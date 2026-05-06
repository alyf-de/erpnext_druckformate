# Copyright (c) 2026, ALYF GmbH and Contributors
# See LICENCE

"""``frappe-pf-init`` CLI: scaffold a Frappe app's ``print_format_sources/`` from a print-format repo.

Usage:
    frappe-pf-init <target_app_path> [--source SOURCE] [--dry-run] [--force]

The target app path must contain ``<app>/<app>/hooks.py``. ``<app>`` is derived from the path.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from erpnext_druckformate_migrator import __version__
from erpnext_druckformate_migrator.hooks_editor import add_hook
from erpnext_druckformate_migrator.ini_to_config import convert as ini_to_config_py
from erpnext_druckformate_migrator.ini_to_config import parse_ini
from erpnext_druckformate_migrator.sass_compile import compile_scss


@dataclass
class TargetApp:
	root: Path  # The repo root that contains <app>/ and pyproject/setup
	app_name: str  # The Frappe app's package name, e.g. "my_app"
	pkg_dir: Path  # <root>/<app_name>/, where hooks.py lives

	@property
	def hooks_py(self) -> Path:
		return self.pkg_dir / "hooks.py"

	@property
	def sources_dir(self) -> Path:
		return self.pkg_dir / "print_format_sources"


@dataclass
class SourceRepo:
	root: Path  # The print-format repo root (contains config.ini)
	config_ini: Path
	scss_path: Path  # First .scss in print_style/, if any
	templates_dir: Path  # print_format/

	@property
	def has_scss(self) -> bool:
		return self.scss_path is not None and self.scss_path.is_file()


@dataclass
class PlannedActions:
	"""What the migrator would do (used for --dry-run output)."""

	created_files: list[Path] = field(default_factory=list)
	hook_messages: list[str] = field(default_factory=list)


class MigrationError(RuntimeError):
	"""Raised for user-facing failures (validation, conflicts, missing inputs)."""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def discover_target_app(target_path: Path) -> TargetApp:
	"""Resolve ``<target_path>`` into a ``TargetApp``.

	The expected layout is a Frappe app: a repo root containing ``<app>/<app>/hooks.py``.
	"""
	target_path = target_path.resolve()
	if not target_path.is_dir():
		raise MigrationError(f"target app path is not a directory: {target_path}")

	# Find candidate app packages: subdirs that contain hooks.py.
	candidates = sorted(
		{p.parent for p in target_path.glob("*/hooks.py") if p.is_file()}
	)
	if not candidates:
		raise MigrationError(
			f"no <app>/hooks.py under {target_path}; pass the repo root of a Frappe app"
		)
	if len(candidates) > 1:
		names = ", ".join(p.name for p in candidates)
		raise MigrationError(
			f"multiple candidate apps under {target_path} ({names}); ambiguous, aborting"
		)
	pkg_dir = candidates[0]
	return TargetApp(root=target_path, app_name=pkg_dir.name, pkg_dir=pkg_dir)


def discover_source_repo(source_path: Path) -> SourceRepo:
	"""Validate that ``source_path`` looks like an erpnext_druckformate-style repo."""
	source_path = source_path.resolve()
	config_ini = source_path / "config.ini"
	if not config_ini.is_file():
		raise MigrationError(
			f"no config.ini at {source_path}; pass --source <path-to-print-format-repo>"
		)
	templates_dir = source_path / "print_format"
	if not templates_dir.is_dir():
		raise MigrationError(f"no print_format/ under {source_path}")

	scss_dir = source_path / "print_style"
	scss_files = sorted(scss_dir.glob("*.scss")) if scss_dir.is_dir() else []
	if len(scss_files) > 1:
		names = ", ".join(p.name for p in scss_files)
		raise MigrationError(
			f"multiple .scss files under {scss_dir} ({names}); migrator expects one shared style"
		)
	scss_path = scss_files[0] if scss_files else None
	return SourceRepo(
		root=source_path,
		config_ini=config_ini,
		scss_path=scss_path,
		templates_dir=templates_dir,
	)


# ---------------------------------------------------------------------------
# Materialization
# ---------------------------------------------------------------------------


def _load_static_template(name: str) -> str:
	"""Read a packaged template file (under ``template_files/``)."""
	return resources.files(
		"erpnext_druckformate_migrator.template_files"
	).joinpath(name).read_text(encoding="utf-8")


def _git_revparse_head(path: Path) -> str:
	"""Return the source repo's HEAD SHA, or 'unknown' if not a git checkout."""
	try:
		out = subprocess.check_output(
			["git", "-C", str(path), "rev-parse", "HEAD"],
			stderr=subprocess.DEVNULL,
		)
		return out.decode().strip()
	except (subprocess.CalledProcessError, FileNotFoundError):
		return "unknown"


def _git_remote_url(path: Path) -> str:
	try:
		out = subprocess.check_output(
			["git", "-C", str(path), "remote", "get-url", "origin"],
			stderr=subprocess.DEVNULL,
		)
		return out.decode().strip()
	except (subprocess.CalledProcessError, FileNotFoundError):
		return "unknown"


def _build_synced_marker(source: SourceRepo) -> str:
	now = datetime.now(timezone.utc).isoformat(timespec="seconds")
	return (
		f"source_url={_git_remote_url(source.root)}\n"
		f"source_commit={_git_revparse_head(source.root)}\n"
		f"synced_at={now}\n"
		f"migrator_version={__version__}\n"
	)


def materialize(
	source: SourceRepo,
	target: TargetApp,
	*,
	dry_run: bool,
	force: bool,
) -> PlannedActions:
	"""Run the migration. Either writes files (default) or just plans them (``dry_run``)."""
	if target.sources_dir.exists() and not force:
		raise MigrationError(
			f"refusing to overwrite existing {target.sources_dir} (use --force to overwrite)"
		)

	# Parse INI early so failures abort before we touch the filesystem.
	formats = parse_ini(source.config_ini)
	for name, spec in formats.items():
		template_src = source.templates_dir / spec["template"]
		if not template_src.is_file():
			# Re-raise with INI section context for a friendlier message.
			raise MigrationError(
				f"[{name}] template not found in source: {template_src}"
			)

	# Compile SCSS up front (also validates it before writing anything).
	if source.has_scss:
		css_text = compile_scss(source.scss_path)
	else:
		css_text = ""

	plan = PlannedActions()

	if not dry_run:
		target.sources_dir.mkdir(parents=True, exist_ok=True)

	# Copy templates.
	for name, spec in formats.items():
		template_src = source.templates_dir / spec["template"]
		template_dst = target.sources_dir / spec["template"]
		plan.created_files.append(template_dst)
		if not dry_run:
			shutil.copyfile(template_src, template_dst)

	# Write CSS.
	css_dst = target.sources_dir / "print_formats.css"
	plan.created_files.append(css_dst)
	if not dry_run:
		css_dst.write_text(css_text, encoding="utf-8")

	# Write config.py.
	config_dst = target.sources_dir / "config.py"
	plan.created_files.append(config_dst)
	if not dry_run:
		config_dst.write_text(ini_to_config_py(source.config_ini), encoding="utf-8")

	# Drop in the static builder + package marker.
	for fname in ("__init__.py", "print_formats.py"):
		dst = target.sources_dir / fname
		plan.created_files.append(dst)
		if not dry_run:
			dst.write_text(_load_static_template(fname), encoding="utf-8")

	# Traceability marker.
	synced_dst = target.sources_dir / ".synced"
	plan.created_files.append(synced_dst)
	if not dry_run:
		synced_dst.write_text(_build_synced_marker(source), encoding="utf-8")

	# Wire up hooks. Both `after_migrate` and `after_install` get an entry pointing
	# at sync_print_formats. Registering directly in hooks.py (instead of editing
	# install.py) means we don't depend on the target app having an install.py.
	target_path = f"{target.app_name}.print_format_sources.print_formats.sync_print_formats"
	for hook_name in ("after_migrate", "after_install"):
		if dry_run:
			plan.hook_messages.append(
				f"would ensure `{hook_name}` in {target.hooks_py} includes {target_path!r}"
			)
		else:
			result = add_hook(target.hooks_py, hook_name, target_path)
			plan.hook_messages.append(f"{result.path}: {result.message}")

	return plan


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


def _print_summary(target: TargetApp, plan: PlannedActions, dry_run: bool) -> None:
	prefix = "[dry-run] " if dry_run else ""
	verb = "would create" if dry_run else "created"
	print(f"\n{prefix}Migrator summary for app '{target.app_name}':")
	print(f"  {verb} {len(plan.created_files)} file(s) under {target.sources_dir}:")
	for p in plan.created_files:
		try:
			rel = p.relative_to(target.root)
		except ValueError:
			rel = p
		print(f"    - {rel}")
	print("  hooks:")
	for m in plan.hook_messages:
		print(f"    - {m}")
	if not dry_run:
		print("\nNext steps:")
		print(f"  1. cd {target.root}")
		print("  2. Review the new files (config.py, print_formats.py, *.jinja, print_formats.css).")
		print("  3. If your templates use custom Jinja helpers (e.g. split_quill), make sure")
		print("     they are exposed via your app's `jinja` hooks.")
		print(f"  4. bench --site <site> migrate    # syncs the print formats")
		print("  5. git add . && git commit -m 'feat: scaffold print_format_sources/'")


def _build_parser() -> argparse.ArgumentParser:
	p = argparse.ArgumentParser(
		prog="frappe-pf-init",
		description=(
			"Scaffold a print_format_sources/ folder into a Frappe app from an "
			"erpnext_druckformate-style print-format repo."
		),
	)
	p.add_argument("target", type=Path,
	               help="Path to the target Frappe app's repo root (containing <app>/<app>/hooks.py)")
	p.add_argument("--source", type=Path, default=Path("."),
	               help="Path to the source print-format repo (default: current directory)")
	p.add_argument("--dry-run", action="store_true",
	               help="Print planned operations without writing")
	p.add_argument("--force", action="store_true",
	               help="Overwrite an existing print_format_sources/ folder")
	p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
	return p


def main(argv: list[str] | None = None) -> int:
	args = _build_parser().parse_args(argv)
	try:
		target = discover_target_app(args.target)
		source = discover_source_repo(args.source)
		plan = materialize(source, target, dry_run=args.dry_run, force=args.force)
	except MigrationError as e:
		print(f"error: {e}", file=sys.stderr)
		return 2
	_print_summary(target, plan, dry_run=args.dry_run)
	return 0


if __name__ == "__main__":
	sys.exit(main())
