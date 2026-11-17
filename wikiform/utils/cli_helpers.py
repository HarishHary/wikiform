from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import click
from loguru import logger

logger = logger.bind(service="Wikiform - CLI")


def resolve_vault_root(ctx: click.Context) -> Path:
    """Return the resolved vault root from the click context, exiting with code 2 if invalid."""
    vault_root = (ctx.obj or {}).get("vault_root")
    if not vault_root:
        logger.error("Vault root path not provided in context")
        raise SystemExit(2)

    root = Path(vault_root).resolve()
    if not root.exists():
        logger.error("Vault root does not exist: {}", root)
        raise SystemExit(2)
    return root


def emit_json(data: Any, output: Path | None, *, label: str = "result") -> None:
    """Write *data* (dataclass or JSON-serialisable) as JSON to *output*, or to stdout when None."""
    payload = asdict(data) if is_dataclass(data) and not isinstance(data, type) else data
    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
        logger.info("Wrote {} to {}", label, output)
    else:
        click.echo(rendered)
