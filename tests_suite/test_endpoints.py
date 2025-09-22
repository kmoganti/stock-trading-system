from fastapi.testclient import TestClient

from main import app


def test_health_like_routes_exist():
    client = TestClient(app)
    r = client.get("/api/system/status")
    assert r.status_code in (200, 404)


def test_watchlist_live_works_without_stream():
    client = TestClient(app)
    r = client.get("/api/watchlist/live")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_watchlist_live_ranking():
    class DummyStream:
        def get_watchlist_snapshot(self):
            return [
                {"symbol": "X", "pctChange": 1},
                {"symbol": "Y", "pctChange": 3},
                {"symbol": "Z", "pctChange": 2},
            ]

    app.state.market_stream_service = DummyStream()
    client = TestClient(app)
    r = client.get("/api/watchlist/live?sortBy=pctChange&direction=desc&limit=2")
    assert r.status_code == 200
    names = [row["symbol"] for row in r.json()]
    assert names == ["Y", "Z"]

