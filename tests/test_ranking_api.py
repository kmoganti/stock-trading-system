from fastapi.testclient import TestClient

from main import app


def test_watchlist_live_endpoint_sort_limit(monkeypatch):
    # Inject a dummy stream service
    class DummyStream:
        def get_watchlist_snapshot(self):
            return [
                {"symbol": "A", "pctChange": 1.0},
                {"symbol": "B", "pctChange": 3.0},
                {"symbol": "C", "pctChange": 2.0},
            ]

    app.state.market_stream_service = DummyStream()

    client = TestClient(app)
    r = client.get("/api/watchlist/live?sortBy=pctChange&direction=desc&limit=2")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    # Should be sorted desc by pctChange: B, C
    assert [row['symbol'] for row in data] == ['B', 'C']
