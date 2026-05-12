"""Seed a minimal deterministic local test dataset."""

from app import create_app
from app.departments.services import ensure_default_departments
from app.extensions import db
from app.models import Department, Role, User
from app.permissions import upsert_default_permissions


def seed_test_data():
    """Create a minimal admin and production user for manual smoke tests."""
    ensure_default_departments()
    department = Department.query.filter_by(name="Produktion").first()
    users = [
        ("test.admin", "test.admin@example.test", Role.MASTER_ADMIN, None),
        ("test.user", "test.user@example.test", Role.PRODUKTION, department),
    ]
    created = 0
    for username, email, role, user_department in users:
        existing = User.query.filter(
            db.or_(User.username == username, User.email == email),
        ).first()
        if existing:
            continue
        user = User(
            username=username,
            email=email,
            role=role,
            department=user_department,
            is_active=True,
        )
        user.set_password("Test1234!")
        db.session.add(user)
        db.session.flush()
        upsert_default_permissions(user)
        created += 1
    db.session.commit()
    return {"users_created": created}


def main():
    """Run deterministic test seeding in the configured application."""
    app = create_app()
    with app.app_context():
        summary = seed_test_data()
    print("Test seed completed:")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
