from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from .dashboard_service import (
    get_dashboard_summary,
    get_spending_by_category,
    get_asset_allocation
)
from ..utils.dashboard_cache import (
    get_cached_dashboard_payload,
    set_cached_dashboard_payload,
)

dashboard_routes = Blueprint(
    "dashboard_routes",
    __name__
)


@dashboard_routes.route("/dashboard/summary", methods=["GET"])
@jwt_required()
def dashboard_summary():

    user_id = int(get_jwt_identity())

    cached, generation, cache_status = get_cached_dashboard_payload(
        user_id, "summary"
    )
    if cached is not None:
        response = jsonify(cached), 200
        # Set a small diagnostic header so local cache behavior is observable.
        response[0].headers["X-Dashboard-Cache"] = cache_status
        return response

    summary = get_dashboard_summary(user_id)
    set_cached_dashboard_payload(
        user_id, "summary", generation, summary
    )
    response = jsonify(summary), 200
    response[0].headers["X-Dashboard-Cache"] = cache_status
    return response


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

    cached, generation, cache_status = get_cached_dashboard_payload(
        user_id, "spending", range_key
    )
    if cached is not None:
        response = jsonify(cached), 200
        response[0].headers["X-Dashboard-Cache"] = cache_status
        return response

    spending = get_spending_by_category(
        user_id,
        range_key
    )
    set_cached_dashboard_payload(
        user_id, "spending", generation, spending, range_key
    )
    response = jsonify(spending), 200
    response[0].headers["X-Dashboard-Cache"] = cache_status
    return response

@dashboard_routes.route("/dashboard/asset-allocation",methods=["GET"])
@jwt_required()
def dashboard_asset_allocation():

    user_id = int(
        get_jwt_identity()
    )

    cached, generation, cache_status = get_cached_dashboard_payload(
        user_id, "asset-allocation"
    )
    if cached is not None:
        response = jsonify(cached), 200
        response[0].headers["X-Dashboard-Cache"] = cache_status
        return response

    allocation = get_asset_allocation(
        user_id
    )
    set_cached_dashboard_payload(
        user_id, "asset-allocation", generation, allocation
    )
    response = jsonify(allocation), 200
    response[0].headers["X-Dashboard-Cache"] = cache_status
    return response
