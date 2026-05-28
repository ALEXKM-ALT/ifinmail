# Architectural exception: CLI developer tooling may import from platform.
# This is a management command only, never executed at runtime in production.
"""Compliance audit command — checks app structure against AGENTS.md."""

import sys
from pathlib import Path

from django.core.management.base import BaseCommand

REQUIRED_FOLDERS = [
    "admin",
    "migrations",
    "models",
    "serializers",
    "services",
    "views",
    "viewsets",
    "tests",
    "fixtures",
    "forms",
    "types",
    "indexes",
    "mixins",
]

REQUIRED_FILES = [
    "api.py",
    "apps.py",
    "assistant_handlers.py",
    "assistant.py",
    "web.py",
    "urls.py",
    "verifications.py",
    "preferences.py",
    "tasks.py",
    "signals.py",
    "hooks.py",
]


class Command(BaseCommand):
    help: str = "Audit all backend apps for AGENTS.md structural compliance."

    def handle(self, **options: object) -> None:
        apps_dir = Path("backend/apps")
        violations = 0

        if not apps_dir.is_dir():
            self.stderr.write(self.style.ERROR("backend/apps/ not found"))
            sys.exit(1)

        apps = sorted(
            p for p in apps_dir.iterdir() if p.is_dir() and not p.name.startswith("_")
        )

        for app_path in apps:
            app_name = app_path.name
            self.stdout.write(f"\n{self.style.SQL_TABLE(app_name)}")

            missing_folders = [
                f
                for f in REQUIRED_FOLDERS
                if not (app_path / f).is_dir()
            ]
            missing_files = [
                f
                for f in REQUIRED_FILES
                if not (app_path / f).is_file()
            ]

            has_models_dir = (app_path / "models").is_dir()
            has_flat_models = (app_path / "models.py").is_file()
            models_ok = has_models_dir and not has_flat_models

            if not models_ok:
                msg = (
                    "models.py file (should be models/ directory)"
                    if has_flat_models
                    else "models/ directory"
                )
                missing_folders.insert(0, f"[MODELS] missing {msg}")

            if missing_folders or missing_files:
                violations += 1
                for f in missing_folders:
                    self.stdout.write(f"  {self.style.ERROR('✗')} missing folder: {f}/")
                for f in missing_files:
                    self.stdout.write(f"  {self.style.WARNING('✗')} missing file: {f}")
            else:
                self.stdout.write(f"  {self.style.SUCCESS('✓')} compliant")

        summary = f"{len(apps)} apps checked, {violations} non-compliant"
        self.stdout.write(f"\n{self.style.SQL_KEYWORD('Summary')}: {summary}")
        sys.exit(0 if violations == 0 else 1)
