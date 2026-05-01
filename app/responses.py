from flask import jsonify


def error_payload(message):
    """Return a consistent API error payload while keeping legacy clients working."""
    text = str(message or "Request failed")
    return {
        "success": False,
        "message": text,
        "error": text,
    }


def error_response(message, status_code=400):
    """Return a Flask JSON response for an API error."""
    return jsonify(error_payload(message)), status_code


def service_error_response(error, status_code=400):
    """Return a normalized error response from a service error payload."""
    if isinstance(error, dict):
        message = error.get("message") or error.get("error") or "Request failed"
    else:
        message = error or "Request failed"
    return error_response(message, status_code)
