from fastapi.testclient import TestClient

from aicfo import __version__
from aicfo.main import create_app


def test_health() -> None:
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == __version__


def test_root_and_favicon_are_not_errors() -> None:
    """Opening the API address in a browser must not show "Not Found"."""
    client = TestClient(create_app())
    root = client.get("/")
    assert root.status_code == 200 and root.json()["docs"] == "/docs"
    assert client.get("/favicon.ico").status_code == 204
