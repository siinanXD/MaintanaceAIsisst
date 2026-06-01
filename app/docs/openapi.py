"""OpenAPI and Swagger UI configuration for the public API surface."""

import logging

from flask import abort, jsonify, redirect, render_template, request
from flask_jwt_extended import verify_jwt_in_request

from app.docs.openapi_parts.builder import build_openapi_spec
from app.models import Role
from app.responses import error_response
from app.security import current_user

logger = logging.getLogger(__name__)

OPENAPI_SPEC = build_openapi_spec()
API_DOCUMENTATION_PATHS = {
    "/swagger/",
    "/api/swagger.json",
    "/api/v1/swagger.json",
    "/apispec_1.json",
}


def hide_route_from_generated_spec(_rule):
    """Keep flasgger from mixing route docstrings into the curated spec."""
    return False


def include_schema_model(_tag):
    """Allow flasgger to expose schema models from the curated template."""
    return True


def api_documentation_enabled(app):
    """Return whether API documentation routes should be registered."""
    if "ENABLE_API_DOCS" in app.config:
        return bool(app.config["ENABLE_API_DOCS"])
    return str(app.config.get("FLASK_ENV", "development")).lower() != "production"


def api_documentation_requires_master_admin(app):
    """Return whether API documentation requests require master admin access."""
    if "API_DOCS_REQUIRE_MASTER_ADMIN" in app.config:
        return bool(app.config["API_DOCS_REQUIRE_MASTER_ADMIN"])
    return str(app.config.get("FLASK_ENV", "development")).lower() == "production"


def require_api_documentation_access(app):
    """Return an error response when the current request cannot access API docs."""
    if request.path not in API_DOCUMENTATION_PATHS:
        return None
    if not api_documentation_enabled(app):
        abort(404)
    if not api_documentation_requires_master_admin(app):
        return None

    verify_jwt_in_request()
    user = current_user()
    if not user or user.role != Role.MASTER_ADMIN:
        return error_response("Forbidden", 403)
    return None


def configure_api_documentation(app):
    """Register OpenAPI JSON and Swagger UI routes on the Flask app."""

    @app.before_request
    def protect_api_documentation_routes():
        """Apply API documentation access policy before serving doc routes."""
        return require_api_documentation_access(app)

    if not api_documentation_enabled(app):
        logger.info("api_documentation_disabled")
        return

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
