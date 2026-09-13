from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from .dashboard_service import (
    get_dashboard_summary,
    get_spending_by_category,
    get_asset_allocation
)

dashboard_routes = Blueprint(
    "dashboard_routes",
    __name__
)


@dashboard_routes.route("/dashboard/summary", methods=["GET"])
@jwt_required()
def dashboard_summary():

    user_id = int(get_jwt_identity())

    summary = get_dashboard_summary(user_id)

    return jsonify(summary), 200


@dashboard_routes.route("/dashboard/spending", methods=["GET"])
@jwt_required()
def dashboard_spending():

    user_id = int(get_jwt_identity())

    range_key = request.args.get(
        "range",
        "30d"
    )

    valid_ranges = {
        "30d",
        "3m",
        "6m",
        "1y",
        "all"
    }

    if range_key not in valid_ranges:
        return jsonify({
            "error": (
                "Invalid range. "
                "Allowed values: "
                "30d, 3m, 6m, 1y, all"
            )
        }), 400

    spending = get_spending_by_category(
        user_id,
        range_key
    )

    return jsonify(spending), 200

@dashboard_routes.route("/dashboard/asset-allocation",methods=["GET"])
@jwt_required()
def dashboard_asset_allocation():

    user_id = int(
        get_jwt_identity()
    )

    allocation = get_asset_allocation(
        user_id
    )

    return jsonify(
        allocation
    ), 200