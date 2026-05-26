"""Compatibility facade for admin API routes."""

# ruff: noqa: F401

from app.admin import ai_routes, system_routes, user_routes
from app.admin.blueprint import admin_bp
from app.admin.route_helpers import database_schema_status

__all__ = ["admin_bp", "database_schema_status"]
