"""Flask CLI commands for scheduled notification jobs."""

import click

from app.services.notification_service import (
    send_ai_alerts,
    send_daily_briefings,
    send_overdue_reminders,
    send_task_alerts,
)


@click.group("notifications")
def notifications_cli():
    """Run notification jobs from a scheduler."""


@notifications_cli.command("send-task-alerts")
def send_task_alerts_command():
    """Send urgent task alerts."""
    click.echo(_format_summary(send_task_alerts()))


@notifications_cli.command("send-overdue-reminders")
def send_overdue_reminders_command():
    """Send overdue task reminders."""
    click.echo(_format_summary(send_overdue_reminders()))


@notifications_cli.command("send-ai-alerts")
def send_ai_alerts_command():
    """Send aggregated AI error alerts."""
    click.echo(_format_summary(send_ai_alerts()))


@notifications_cli.command("send-daily-briefings")
def send_daily_briefings_command():
    """Send daily briefing emails."""
    click.echo(_format_summary(send_daily_briefings()))


def register_notification_commands(app):
    """Register notification CLI commands on the Flask app."""
    app.cli.add_command(notifications_cli)


def _format_summary(summary):
    """Return a compact one-line job summary."""
    return (
        f"{summary['notification_type']}: scanned={summary['scanned']} "
        f"deliveries_created={summary['deliveries_created']}"
    )
