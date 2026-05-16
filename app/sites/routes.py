"""Site API routes."""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.responses import success_response
from app.services.site_service import list_sites

sites_bp = Blueprint("sites", __name__)


@sites_bp.get("")
@jwt_required()
def sites():
    """Return active sites for selectors and operations filters."""
    include_inactive = str(request.args.get("include_inactive", "")).lower() in {
        "1",
        "true",
        "yes",
    }
    return success_response(
        [site.to_dict() for site in list_sites(include_inactive=include_inactive)],
        message="Sites loaded",
    )
