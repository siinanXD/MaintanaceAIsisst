"""Administrative Flask CLI commands."""

from pathlib import Path

import click

from app.services.backup_service import create_backup, restore_backup


@click.group("admin")
def admin_cli():
    """Run administrative maintenance commands."""


@admin_cli.command("backup")
def backup_command():
    """Create a backup ZIP for database and configured file folders."""
    metadata = create_backup(reason="cli")
    click.echo(f"Backup created: {metadata['filename']}")


@admin_cli.command("restore")
@click.argument("backup_file")
@click.option("--confirm", is_flag=True, help="Confirm replacing local data from backup.")
def restore_command(backup_file, confirm):
    """Restore a backup ZIP by filename or absolute path."""
    if not confirm:
        raise click.ClickException("Use --confirm to restore a backup")
    backup_path = Path(backup_file)
    backup_id = backup_path.name
    result, error, status = restore_backup(backup_id, confirm=True)
    if error:
        raise click.ClickException(f"{status}: {error['error']}")
    click.echo(f"Backup restored: {result['restored_backup']}")


def register_admin_commands(app):
    """Register administrative CLI commands on the Flask app."""
    app.cli.add_command(admin_cli)
