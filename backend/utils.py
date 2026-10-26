"""Compatibility helpers for the generated API module."""

from functools import wraps

from flask import jsonify, session


def token_required(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"message": "Authentication required"}), 401
        return handler(session["user_id"], *args, **kwargs)

    return wrapped
