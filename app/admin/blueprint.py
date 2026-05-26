"""Shared admin API blueprint."""

from flask import Blueprint

admin_bp = Blueprint("admin", __name__)

__all__ = ["admin_bp"]
