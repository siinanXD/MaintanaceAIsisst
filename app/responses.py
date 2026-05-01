from flask import jsonify


def error_code_from_message(message):
    """Return a short stable error code from a human-readable message."""
    text = str(message or "request failed").strip().lower()
    code = []
    for character in text:
        if character.isalnum():
            code.append(character)
        elif code and code[-1] != "_":
            code.append("_")
    normalized = "".join(code).strip("_")
    return normalized[:80] or "request_failed"


def error_payload(message):
    """Return a consistent API error payload."""
    text = str(message or "Request failed")
    return {
        "success": False,
        "message": text,
        "error": error_code_from_message(text),
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


def success_payload(data=None, message="OK"):
    """Return a consistent API success payload."""
    payload = {
        "success": True,
        "data": data,
        "message": message,
    }
    if isinstance(data, dict):
        payload.update(data)
    return payload


def success_response(data=None, status_code=200, message="OK"):
    """Return a Flask JSON response for a successful API operation."""
    return jsonify(success_payload(data, message)), status_code
