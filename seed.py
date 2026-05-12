"""Seed the local database with the selected data profile."""

import argparse

from seed_demo import main as seed_demo_main
from seed_production import main as seed_production_main
from seed_test import main as seed_test_main

SEED_MODES = {
    "demo": seed_demo_main,
    "production": seed_production_main,
    "test": seed_test_main,
}


def main():
    """Run the selected seed mode."""
    parser = argparse.ArgumentParser(description="Seed Maintenance Assistant data")
    parser.add_argument(
        "mode",
        nargs="?",
        choices=sorted(SEED_MODES),
        default="demo",
        help="Seed profile to run",
    )
    args = parser.parse_args()
    SEED_MODES[args.mode]()


if __name__ == "__main__":
    main()
