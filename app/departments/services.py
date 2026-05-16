"""Department service helpers."""

from app.extensions import db
from app.models import Department
from app.services.site_service import ensure_default_site

DEFAULT_DEPARTMENTS = ["IT", "Verwaltung", "Instandhaltung", "Produktion"]


def ensure_default_departments():
    """Create missing built-in departments."""
    site = ensure_default_site()
    for name in DEFAULT_DEPARTMENTS:
        department = Department.query.filter_by(name=name).first()
        if not department:
            db.session.add(Department(name=name, site=site))
        elif department.site_id is None:
            department.site = site
    db.session.commit()


def create_department(name):
    """Create a department and return a service-style result tuple."""
    if not name:
        return None, {"error": "name is required"}, 400
    existing = Department.query.filter_by(name=name).first()
    if existing:
        return None, {"error": "Department already exists"}, 409
    department = Department(name=name, site=ensure_default_site())
    db.session.add(department)
    db.session.commit()
    return department, None, 201
