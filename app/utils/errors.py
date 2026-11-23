"""Uniform JSON error replies that never expose server internals.

Exception text can contain SQL statements, table and constraint names, file
paths or library details. Those are useful to an attacker and meaningless to
the user, so they go to the server log (Render's log stream) and the client
gets a generic message.
"""

from flask import current_app, jsonify, request
from werkzeug.exceptions import InternalServerError, RequestEntityTooLarge


GENERIC_SERVER_ERROR = "Something went wrong on our side. Please try again."


def server_error():
    """Call from inside an ``except`` block: logs the traceback, returns 500."""
    current_app.logger.exception(
        "Unhandled error in %s %s", request.method, request.endpoint
    )
    return jsonify({"error": GENERIC_SERVER_ERROR}), 500


def _request_too_large(error):
    limit_kb = current_app.config["MAX_CONTENT_LENGTH"] // 1024
    return jsonify({"error": f"Request is too large (limit {limit_kb} KB)."}), 413


def _unhandled_server_error(error):
    # Exceptions no view caught. Flask has already logged the traceback.
    return jsonify({"error": GENERIC_SERVER_ERROR}), 500


def register_error_handlers(app):
    app.register_error_handler(RequestEntityTooLarge, _request_too_large)
    app.register_error_handler(InternalServerError, _unhandled_server_error)
