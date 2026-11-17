from __future__ import annotations

from pathlib import Path

SCHEMA_FILE = "SCHEMA.md"


def is_vault(path: Path) -> bool:
    return (path / SCHEMA_FILE).is_file()


def find_vault_root(start: Path, max_up: int = 3) -> Path | None:
    """Find the nearest directory containing SCHEMA.md, looking at *start* and up to *max_up* parents."""
    start = start.resolve()
    if start.is_file():
        start = start.parent
    for candidate in [start, *start.parents][: max_up + 1]:
        if is_vault(candidate):
            return candidate
    return None


def resolve_vault(configured: str | None, start: Path | None, max_up: int = 3) -> Path | None:
    """Vault lookup order: configured root (if it holds a SCHEMA.md), then a walk up from *start*."""
    if configured:
        root = Path(configured).expanduser().resolve()
        if is_vault(root):
            return root
    if start is not None:
        return find_vault_root(start, max_up)
    return None
