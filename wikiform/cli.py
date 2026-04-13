import sys
import click
import logging
from loguru import logger
from wikiform.cmd.index import index_cmd
from wikiform.cmd.lint import lint_cmd
from wikiform.cmd.query import query_cmd
from wikiform.cmd.fts_index import fts_index_cmd
from wikiform.cmd.serve import serve_cmd

# Remove default loguru handler
logger.remove()
logger = logger.bind(service="Wikiform - CLI")


@click.group(invoke_without_command=True)
@click.version_option()
@click.option("--logging-file", help="The filepath used for wikiform's logging.")
@click.option("--vault-root", required=True, help="Vault root path")
@click.option("-v", "--verbose", default=False, is_flag=True, help="Enable debug verbosity.")
@click.pass_context
def cli(ctx: click.Context, logging_file: str | None, verbose: bool, vault_root: str) -> None:
    ctx.ensure_object(dict)
    ctx.obj["vault_root"] = vault_root

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        return
    verbosity = "INFO"
    if verbose:
        verbosity = "DEBUG"

    logger.remove()  # clear any sinks added by previous invocations (e.g. in tests)
    if logging_file:
        # File log (no colors)
        logger.add(
            logging_file,
            level=verbosity,
            rotation="500 KB",
            retention="10 days",
            enqueue=True,
            format="{time:YYYY-MM-DD HH:mm:ss} [{level}][{extra[service]}]: {message}",
        )
    else:
        # Terminal log (colorized) → stderr so stdout stays clean JSON
        logger.add(
            sink=sys.stderr,
            level=verbosity,
            colorize=True,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> <level>[{level}][{extra[service]}]: {message}</level>",
        )

    # Suppress third-party stdlib logging
    logging.getLogger().setLevel(logging.CRITICAL)
    logging.captureWarnings(True)


@cli.group("search", help="Full-text search: build fts-index, query, and serve.")
def search_group() -> None:
    """Search subcommands."""


search_group.add_command(fts_index_cmd, name="index")
search_group.add_command(query_cmd)
search_group.add_command(serve_cmd)

cli.add_command(index_cmd)
cli.add_command(lint_cmd)
cli.add_command(search_group)
