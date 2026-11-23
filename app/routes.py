from datetime import datetime

from flask import (
    Blueprint,
    jsonify,
    request,
    send_file,
)

from flask_jwt_extended import (
    get_jwt_identity,
    jwt_required,
)

from . import db
from .models import User

from .utils.transaction_export_util import (
    CATEGORY_ORDER,
    create_transaction_excel,
    create_transaction_pdf,
    normalize_export_categories,
)

routes = Blueprint('routes', __name__)

# Home route
@routes.route('/')
def home():
    return "Welcome to the Personal Portfolio App!"

# ============================================================
# TRANSACTION EXPORT ROUTES
# ============================================================

def _get_authorized_export_user(user_id):
    user = db.session.get(
        User,
        user_id,
    )

    if user is None:
        return None, (
            jsonify({
                "error": "User not found"
            }),
            404,
        )

    current_user_id = int(
        get_jwt_identity()
    )

    if user_id != current_user_id:
        return None, (
            jsonify({
                "error": "Unauthorized"
            }),
            403,
        )

    return user, None


def _get_requested_export_categories():
    values = request.args.getlist(
        "categories"
    )

    return normalize_export_categories(
        values
    )


def _export_error_response():
    return jsonify({
        "error": (
            "Unable to generate "
            "transaction backup"
        )
    }), 500


@routes.route(
    "/users/<int:id>/transactions/export/excel",
    methods=["GET"],
)
@jwt_required()
def export_user_transactions_excel(id):
    user, error_response = (
        _get_authorized_export_user(id)
    )

    if error_response:
        return error_response

    try:
        categories = (
            _get_requested_export_categories()
        )
    except ValueError as exc:
        return jsonify({
            "error": str(exc),
            "allowed_categories": [
                "all",
                *CATEGORY_ORDER,
            ],
        }), 400

    try:
        output = create_transaction_excel(
            user.id,
            categories,
        )

        category_label = (
            "all"
            if categories
            == list(CATEGORY_ORDER)
            else "selected"
        )

        filename = (
            "transaction_backup_"
            f"{category_label}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            ".xlsx"
        )

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype=(
                "application/"
                "vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

    except Exception:
        db.session.rollback()

        return _export_error_response()


@routes.route(
    "/users/<int:id>/transactions/export/pdf",
    methods=["GET"],
)
@jwt_required()
def export_user_transactions_pdf(id):
    user, error_response = (
        _get_authorized_export_user(id)
    )

    if error_response:
        return error_response

    try:
        categories = (
            _get_requested_export_categories()
        )
    except ValueError as exc:
        return jsonify({
            "error": str(exc),
            "allowed_categories": [
                "all",
                *CATEGORY_ORDER,
            ],
        }), 400

    try:
        output = create_transaction_pdf(
            user.id,
            categories,
        )

        category_label = (
            "all"
            if categories
            == list(CATEGORY_ORDER)
            else "selected"
        )

        filename = (
            "transaction_backup_"
            f"{category_label}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            ".pdf"
        )

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/pdf",
        )

    except Exception:
        db.session.rollback()

        return _export_error_response()
