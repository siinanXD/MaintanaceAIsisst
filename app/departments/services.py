"""Department service helpers."""

from app.extensions import db
from app.models import Department

DEFAULT_DEPARTMENTS = ["IT", "Verwaltung", "Instandhaltung", "Produktion"]


def ensure_default_departments():
    """Create missing built-in departments."""
    for name in DEFAULT_DEPARTMENTS:
        if not Department.query.filter_by(name=name).first():
            db.session.add(Department(name=name))
    db.session.commit()


def create_department(name):
    """Create a department and return a service-style result tuple."""
    if not name:
        return None, {"error": "name is required"}, 400
    existing = Department.query.filter_by(name=name).first()
    if existing:
        return None, {"error": "Department already exists"}, 409
    department = Department(name=name)
    db.session.add(department)
    db.session.commit()
    return department, None, 201
