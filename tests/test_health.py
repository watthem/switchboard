"""Tests for app-level endpoints: /health, /dashboard, /docs/shared.css."""


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


def test_dashboard_returns_html(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "herald" in resp.text.lower()


def test_shared_css_returns_css(client):
    resp = client.get("/docs/shared.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]
