from app import create_app
from app.demo_data import seed_demo_data


def main():
    """Seed the local database with realistic demo data."""
    app = create_app()
    with app.app_context():
        summary = seed_demo_data()
    print("Demo data seeded:")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
