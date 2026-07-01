import pytest


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Never actually sleep during tests."""
    import writeGoogleSheet
    monkeypatch.setattr(writeGoogleSheet, "sleep", lambda *_a, **_k: None)


@pytest.fixture
def fake_config(monkeypatch):
    """Swap in a small, deterministic config dict for a single test."""
    import writeGoogleSheet
    cfg = {
        "google": {"max_tries": 3},
        "cambristi": {
            "members_endpoint": "https://example.test/members/",
            "orders_endpoint": "https://example.test/orders/",
            "activities_endpoint": "https://example.test/activities/",
            "groups_endpoint": "https://example.test/groups/",
            "participants_endpoint": "https://example.test/participants/",
        },
        "geomap": {"index": "/tmp/geomap.html"},
        "logs": {"days": 7},
    }
    monkeypatch.setattr(writeGoogleSheet, "config", cfg)
    monkeypatch.setattr(writeGoogleSheet, "max_tries", cfg["google"]["max_tries"])
    return cfg
