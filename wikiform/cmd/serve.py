from __future__ import annotations

from pathlib import Path

import click
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from loguru import logger

from wikiform.cmd.query import SearchResult, run_query
from wikiform.utils.db import db_path

logger = logger.bind(service="Wikiform - Serve")

_SEARCH_UI = """<!DOCTYPE html>
<html><head><title>Vault Search</title>
<style>
body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; background: #1e1e1e; color: #d4d4d4; }
input { width: 100%; padding: 12px; font-size: 16px; border: 1px solid #444; border-radius: 8px; background: #2d2d2d; color: #d4d4d4; box-sizing: border-box; }
.result { padding: 12px; margin: 8px 0; border: 1px solid #333; border-radius: 6px; background: #252525; }
.result h3 { margin: 0 0 4px; color: #569cd6; }
.result .path { color: #888; font-size: 0.85em; }
.result .snippet { margin-top: 6px; }
.result .snippet b { color: #dcdcaa; }
.tags { color: #6a9955; font-size: 0.85em; }
</style></head><body>
<h1>Vault Search</h1>
<input type="text" id="q" placeholder="Search your knowledge base..." autofocus>
<div id="results"></div>
<script>
let timer;
document.getElementById('q').addEventListener('input', e => {
    clearTimeout(timer);
    const q = e.target.value.trim();
    if (!q) { document.getElementById('results').textContent = ''; return; }
    timer = setTimeout(() => {
        fetch('/search?q=' + encodeURIComponent(q))
            .then(r => r.json())
            .then(data => {
                const container = document.getElementById('results');
                container.textContent = '';
                if (!data.length) {
                    const msg = document.createElement('p');
                    msg.style.color = '#888';
                    msg.textContent = 'No results.';
                    container.appendChild(msg);
                    return;
                }
                data.forEach(r => {
                    const div = document.createElement('div');
                    div.className = 'result';
                    const h3 = document.createElement('h3');
                    h3.textContent = r.title || r.path;
                    const pathEl = document.createElement('div');
                    pathEl.className = 'path';
                    pathEl.textContent = r.path;
                    const tagsEl = document.createElement('div');
                    tagsEl.className = 'tags';
                    tagsEl.textContent = r.tags || '';
                    // FTS5 wraps matches in <b>...</b> - build with DOM nodes, no innerHTML
                    const snippetEl = document.createElement('div');
                    snippetEl.className = 'snippet';
                    (r.snippet || '').split(/(<b>[^<]*<\\/b>)/).forEach(part => {
                        const m = part.match(/^<b>([^<]*)<\\/b>$/);
                        if (m) { const b = document.createElement('b'); b.textContent = m[1]; snippetEl.appendChild(b); }
                        else { snippetEl.appendChild(document.createTextNode(part)); }
                    });
                    div.appendChild(h3); div.appendChild(pathEl); div.appendChild(tagsEl); div.appendChild(snippetEl);
                    container.appendChild(div);
                });
            })
            .catch(() => {});
    }, 300);
});
</script></body></html>"""


def build_app(vault_root: Path) -> FastAPI:
    app = FastAPI(title="Vault Search")

    @app.get("/", response_class=HTMLResponse)
    async def home() -> str:
        return _SEARCH_UI

    @app.get("/search")
    async def api_search(q: str, limit: int = Query(default=20, ge=1, le=100)) -> list[SearchResult]:
        try:
            return run_query(vault_root, q, limit=limit)
        except ValueError as exc:
            logger.warning("Search error for query {!r}: {}", q, exc)
            return []

    return app


@click.command("serve")
@click.option("--port", default=8787, show_default=True, help="Port for web UI")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host to bind (default: localhost only)")
@click.pass_context
def serve_cmd(ctx: click.Context, port: int, host: str) -> None:
    vault_root = ctx.obj.get("vault_root")
    if not vault_root:
        logger.error("Vault root path not provided in context")
        raise SystemExit(2)

    root = Path(vault_root).resolve()
    if not root.exists():
        logger.error("Vault root does not exist: {}", root)
        raise SystemExit(2)

    if not db_path(root).exists():
        logger.warning("No search index found at {}. Run 'wikiform search index' first.", db_path(root))

    app = build_app(root)
    logger.info("Vault Search running at http://{}:{}", host, port)
    uvicorn.run(app, host=host, port=port, log_level="warning")
