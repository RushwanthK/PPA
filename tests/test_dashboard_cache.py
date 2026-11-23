from app.dashboard import dashboard_routes as dashboard_routes_module
from app.utils.dashboard_cache import (
    get_cached_dashboard_payload,
    invalidate_dashboard_cache,
    set_cached_dashboard_payload,
)


class MemoryRedis:
    """Small deterministic fake for dashboard cache tests; no Redis server needed."""

    def __init__(self):
        self.values = {}
        self.expiries = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = str(value)
        if ex is not None:
            self.expiries[key] = ex
        return True


class FailingRedis:
    def get(self, key):
        raise ConnectionError("simulated Redis outage")



def test_dashboard_cache_hit_avoids_recomputing_summary(
    app, authenticated_client, monkeypatch
):
    fake_redis = MemoryRedis()
    monkeypatch.setitem(app.extensions, "ppa_dashboard_redis", fake_redis)
    calls = {"count": 0}
    expected = {
        "total_assets": 1.0,
        "total_bank_balance": 2.0,
        "total_savings": 3.0,
        "total_credit_card_debt": 4.0,
        "net_worth": 2.0,
    }

    def compute_summary(user_id):
        calls["count"] += 1
        return expected

    monkeypatch.setattr(
        dashboard_routes_module, "get_dashboard_summary", compute_summary
    )

    first = authenticated_client.get("/dashboard/summary")
    second = authenticated_client.get("/dashboard/summary")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json() == expected
    assert second.get_json() == expected
    assert first.headers["X-Dashboard-Cache"] == "MISS"
    assert second.headers["X-Dashboard-Cache"] == "HIT"
    assert calls["count"] == 1



def test_dashboard_cache_invalidation_makes_old_entries_unreachable(
    app, monkeypatch
):
    fake_redis = MemoryRedis()
    monkeypatch.setitem(app.extensions, "ppa_dashboard_redis", fake_redis)

    with app.app_context():
        payload, generation, status = get_cached_dashboard_payload(42, "summary")
        assert payload is None
        assert status == "MISS"

        original = {"net_worth": 100.0}
        assert set_cached_dashboard_payload(42, "summary", generation, original)

        cached, _, status = get_cached_dashboard_payload(42, "summary")
        assert cached == original
        assert status == "HIT"

        assert invalidate_dashboard_cache(42)
        cached, _, status = get_cached_dashboard_payload(42, "summary")
        assert cached is None
        assert status == "MISS"

        # A different user's namespace remains isolated.
        other, _, other_status = get_cached_dashboard_payload(43, "summary")
        assert other is None
        assert other_status == "MISS"



def test_dashboard_endpoint_falls_back_when_redis_is_unavailable(
    app, authenticated_client, monkeypatch
):
    monkeypatch.setitem(app.extensions, "ppa_dashboard_redis", FailingRedis())
    expected = {
        "total_assets": 0.0,
        "total_bank_balance": 0.0,
        "total_savings": 0.0,
        "total_credit_card_debt": 0.0,
        "net_worth": 0.0,
    }
    monkeypatch.setattr(
        dashboard_routes_module,
        "get_dashboard_summary",
        lambda user_id: expected,
    )

    response = authenticated_client.get("/dashboard/summary")

    assert response.status_code == 200
    assert response.get_json() == expected
    assert response.headers["X-Dashboard-Cache"] == "BYPASS"



def test_bank_transaction_invalidates_cached_dashboard_summary(
    app, authenticated_client, test_bank, monkeypatch
):
    fake_redis = MemoryRedis()
    monkeypatch.setitem(app.extensions, "ppa_dashboard_redis", fake_redis)

    first = authenticated_client.get("/dashboard/summary")
    assert first.status_code == 200
    assert first.headers["X-Dashboard-Cache"] == "MISS"
    assert first.get_json()["total_bank_balance"] == 10000.0

    write_response = authenticated_client.post(
        f"/banks/{test_bank.id}/transactions",
        json={
            "amount": 500,
            "type": "expense",
            "description": "Cache invalidation test",
            "category": "Testing",
        },
    )
    assert write_response.status_code == 201

    second = authenticated_client.get("/dashboard/summary")
    assert second.status_code == 200
    assert second.headers["X-Dashboard-Cache"] == "MISS"
    assert second.get_json()["total_bank_balance"] == 9500.0
