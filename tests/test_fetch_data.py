from unittest.mock import patch

import requests

import writeGoogleSheet as wgs


@patch("writeGoogleSheet.requests.get")
def test_fetch_data_200_returns_json(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"items": [1, 2]}
    assert wgs.fetch_data("http://x", "tok") == {"items": [1, 2]}


@patch("writeGoogleSheet.requests.get")
def test_fetch_data_non_200_returns_none(mock_get):
    mock_get.return_value.status_code = 404
    assert wgs.fetch_data("http://x", "tok") is None


@patch("writeGoogleSheet.requests.get")
def test_fetch_data_retries_on_request_exception_then_gives_up(mock_get, fake_config):
    mock_get.side_effect = requests.exceptions.RequestException("timeout")
    assert wgs.fetch_data("http://x", "tok") is None
    assert mock_get.call_count == fake_config["google"]["max_tries"]


@patch("writeGoogleSheet.requests.get")
def test_fetch_data_recovers_after_transient_exception(mock_get):
    ok_response = type("R", (), {"status_code": 200, "json": lambda self: {"ok": True}})()
    mock_get.side_effect = [requests.exceptions.RequestException("timeout"), ok_response]
    assert wgs.fetch_data("http://x", "tok") == {"ok": True}
