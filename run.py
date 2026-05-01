import argparse
import os

from app import create_app


app = create_app()


def debug_enabled():
    """Return whether the local development server should run in debug mode."""
    explicit_debug = os.getenv("FLASK_DEBUG")
    if explicit_debug is not None:
        return explicit_debug.lower() in {"1", "true", "yes", "on"}
    return os.getenv("FLASK_ENV", "development").lower() == "development"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Maintenance Assistant API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=5050, type=int)
    parser.add_argument(
        "--https",
        action="store_true",
        help="Run local development server with an ad-hoc self-signed HTTPS certificate.",
    )
    args = parser.parse_args()

    ssl_context = "adhoc" if args.https else None
    app.run(
        host=args.host,
        port=args.port,
        debug=debug_enabled(),
        ssl_context=ssl_context,
        use_reloader=False,
    )
