"""OpenAPI and Swagger UI configuration for the public API surface."""

import logging

from flask import jsonify, redirect, render_template

from app.docs.openapi_parts.builder import build_openapi_spec

logger = logging.getLogger(__name__)

OPENAPI_SPEC = build_openapi_spec()


def hide_route_from_generated_spec(_rule):
    """Keep flasgger from mixing route docstrings into the curated spec."""
    return False


def include_schema_model(_tag):
    """Allow flasgger to expose schema models from the curated template."""
    return True


def configure_api_documentation(app):
    """Register OpenAPI JSON and Swagger UI routes on the Flask app."""

    @app.get("/api/swagger.json")
    def swagger_json():
        """Return the OpenAPI specification as JSON."""
        return jsonify(OPENAPI_SPEC)

    @app.get("/api/v1/swagger.json")
    def swagger_json_legacy_redirect():
        """Redirect the deprecated v1 OpenAPI URL to the canonical JSON route."""
        return redirect("/api/swagger.json", code=308)

    try:
        from flasgger import Swagger
    except ImportError:
        logger.warning("flasgger_missing swagger_ui=fallback")

        @app.get("/swagger/")
        def swagger_fallback():
            """Render a lightweight Swagger UI fallback using the OpenAPI JSON."""
            return render_template("swagger.html")

        return

    Swagger(
        app,
        template=OPENAPI_SPEC,
        config={
            "headers": [],
            "specs": [
                {
                    "endpoint": "apispec",
                    "route": "/apispec_1.json",
                    "rule_filter": hide_route_from_generated_spec,
                    "model_filter": include_schema_model,
                }
            ],
            "static_url_path": "/flasgger_static",
            "swagger_ui": True,
            "specs_route": "/swagger/",
        },
    )
