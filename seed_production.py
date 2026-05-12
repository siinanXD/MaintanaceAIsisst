"""Seed production-safe baseline data without demo credentials."""

import os

from app import create_app
from app.departments.services import ensure_default_departments
from app.extensions import db
from app.models import Role, User
from app.permissions import upsert_default_permissions


def seed_production_data():
    """Create default departments and an optional bootstrap admin."""
    ensure_default_departments()
    username = os.getenv("ADMIN_USERNAME", "").strip()
    email = os.getenv("ADMIN_EMAIL", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    created_admin = False

    if username and email and password:
        user = User.query.filter(
            db.or_(User.username == username, User.email == email),
        ).first()
        if not user:
            user = User(
                username=username,
                email=email,
                role=Role.MASTER_ADMIN,
                is_active=True,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            upsert_default_permissions(user)
            db.session.commit()
            created_admin = True

    return {
        "departments": "ensured",
        "admin_created": created_admin,
    }


def main():
    """Run production-safe seeding in the configured application."""
    app = create_app()
    with app.app_context():
        summary = seed_production_data()
    print("Production seed completed:")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
