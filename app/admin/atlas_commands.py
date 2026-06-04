"""Flask CLI commands for MongoDB Atlas Vector Search maintenance."""

import click

from app.services.atlas_health_service import (
    atlas_vector_store_health,
    ensure_atlas_vector_index,
    probe_atlas_vector_search,
)


@click.group("atlas")
def atlas_cli():
    """Manage MongoDB Atlas Vector Search indexes and health checks."""


@atlas_cli.command("ensure-index")
def ensure_index_command():
    """Create the configured Atlas vector index when it is missing."""
    result = ensure_atlas_vector_index()
    if not result.get("ok"):
        raise click.ClickException(result.get("reason") or "Atlas index setup failed")
    click.echo(
        f"Atlas vector index {result.get('index_name')}: {result.get('status')} "
        f"(dimensions={result.get('dimensions')})"
    )


@atlas_cli.command("health")
def health_command():
    """Print prompt-safe Atlas vector-store health diagnostics."""
    health = atlas_vector_store_health()
    click.echo(
        f"configured={health['configured']} active={health['active']} "
        f"connected={health['connected']} index_ready={health['index_ready']} "
        f"fallback_active={health['fallback_active']} reason={health['reason']}"
    )
    if not health.get("ok", False):
        raise click.ClickException(health.get("reason") or "Atlas health check failed")


@atlas_cli.command("probe-search")
def probe_search_command():
    """Run a lightweight Atlas vector search probe."""
    result = probe_atlas_vector_search()
    click.echo(f"ok={result['ok']} reason={result['reason']} latency_ms={result['latency_ms']}")
    if not result.get("ok"):
        raise click.ClickException(result.get("reason") or "Atlas vector search probe failed")


def register_atlas_commands(app):
    """Register Atlas CLI commands on the Flask app."""
    app.cli.add_command(atlas_cli)
