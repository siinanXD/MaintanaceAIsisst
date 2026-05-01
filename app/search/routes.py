from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.responses import error_response
from app.security import current_user
from app.services.search_service import search_knowledge


search_bp = Blueprint("search", __name__)


@search_bp.get("")
@jwt_required()
def search():
    """Search visible tasks, errors and generated document metadata."""
    query = request.args.get("q", "").strip()
    if not query:
        return error_response("q is required", 400)
    return jsonify(search_knowledge(query, current_user()))
