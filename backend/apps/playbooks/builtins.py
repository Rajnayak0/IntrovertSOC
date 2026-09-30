"""Built-in playbook definitions loaded from data/playbooks/*.yaml (MIGRATION #6).

get_or_create by name, so re-syncing never clobbers user edits of built-ins.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from django.conf import settings

from .models import Playbook

logger = logging.getLogger("apps.playbooks")


def builtin_dir() -> Path:
    return Path(settings.BASE_DIR) / "data" / "playbooks"


def sync_builtins() -> int:
    created = 0
    directory = builtin_dir()
    if not directory.exists():
        return 0
    for path in sorted(directory.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            logger.warning("skipping playbook %s: %s", path.name, exc)
            continue
        name = str(data.get("name") or path.stem).strip()
        if not name:
            continue
        _, was_created = Playbook.objects.get_or_create(
            name=name,
            defaults={
                "description": str(data.get("description", "")),
                "definition": path.read_text(encoding="utf-8"),
                "enabled": bool(data.get("enabled", True)),
                "builtin": True,
            },
        )
        if was_created:
            created += 1
    return created
