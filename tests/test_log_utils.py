from unittest.mock import patch

import writeGoogleSheet as wgs


@patch("writeGoogleSheet.logging.info")
def test_log_valid_severity_dispatches(mock_info):
    wgs.log("info", "hello")
    mock_info.assert_called_once_with("hello")


@patch("writeGoogleSheet.logging.error")
@patch("writeGoogleSheet.logging.info")
def test_log_invalid_severity_falls_back(mock_info, mock_error):
    wgs.log("bogus", "hello")
    mock_error.assert_called_once()
    mock_info.assert_called_once_with("hello")


@patch("writeGoogleSheet.requests.post")
def test_send_log_request_success_no_error_logged(mock_post):
    mock_post.return_value.status_code = 201
    with patch("writeGoogleSheet.logging.error") as mock_error:
        wgs.send_log_request("http://x", "hash", "tag", {}, {"a": 1})
    mock_error.assert_not_called()
    mock_post.assert_called_once_with(
        "http://x?token=hash&tag=tag", headers={}, json={"a": 1}
    )


@patch("writeGoogleSheet.requests.post")
def test_send_log_request_non_201_logs_error(mock_post):
    mock_post.return_value.status_code = 500
    mock_post.return_value.text = "boom"
    with patch("writeGoogleSheet.logging.error") as mock_error:
        wgs.send_log_request("http://x", "hash", "tag", {}, {})
    mock_error.assert_called_once()


@patch("writeGoogleSheet.requests.post", side_effect=RuntimeError("network down"))
def test_send_log_request_exception_is_caught(_mock_post):
    with patch("writeGoogleSheet.logging.exception") as mock_exc:
        wgs.send_log_request("http://x", "hash", "tag", {}, {})
    mock_exc.assert_called_once()
