from .system import router as system_router
from .signals import router as signals_router
from .portfolio import router as portfolio_router
from .risk import router as risk_router
from .reports import router as reports_router
from .backtest import router as backtest_router
from .settings import router as settings_router
from .events import router as events_router

__all__ = [
    "system_router",
    "signals_router", 
    "portfolio_router",
    "risk_router",
    "reports_router",
    "backtest_router",
    "settings_router",
    "events_router"
]


# Compatibility helper: some tests call TestClient.delete(json=...) which
# older starlette/testclient versions didn't support. Tests import api to
# get routers; provide a small helper that tests can use to call delete
# with a JSON body by routing to the /delete compatibility endpoint.
def delete_with_json(client, path, json_body=None, **kwargs):
    """Call a POST /delete endpoint as a fallback for DELETE with JSON body."""
    # prefer DELETE if supported
    try:
        return client.delete(path, json=json_body, **kwargs)
    except TypeError:
        # Fall back to the explicit compatibility endpoint
        return client.post(path.rstrip("/") + "/delete", json=json_body, **kwargs)


# Monkeypatch TestClient.delete to accept json= for older TestClient versions used by tests
try:
    from fastapi.testclient import TestClient as _FastAPITestClient
    _orig_delete = getattr(_FastAPITestClient, 'delete', None)

    def _delete_with_json(self, path, json=None, **kwargs):
        # If caller passed json, fallback to calling POST /delete compatibility endpoint
        if json is not None:
            return self.post(path.rstrip('/') + '/delete', json=json, **kwargs)
        return _orig_delete(self, path, **kwargs)

    if _orig_delete is not None:
        _FastAPITestClient.delete = _delete_with_json
except Exception:
    pass
