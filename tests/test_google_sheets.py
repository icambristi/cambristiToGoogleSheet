from unittest.mock import MagicMock, patch

import gspread
import pytest

import writeGoogleSheet as wgs


def _api_error_429():
    resp = MagicMock()
    resp.json.return_value = {"error": {"code": 429, "message": "quota exceeded", "status": "RESOURCE_EXHAUSTED"}}
    return gspread.exceptions.APIError(resp)


def _api_error_500():
    resp = MagicMock()
    resp.json.return_value = {"error": {"code": 500, "message": "server error", "status": "INTERNAL"}}
    return gspread.exceptions.APIError(resp)


def test_retry_on_quota_returns_result_on_first_success():
    fn = MagicMock(return_value="ok")
    assert wgs._retry_on_quota(fn, "a", b=1) == "ok"
    fn.assert_called_once_with("a", b=1)


def test_retry_on_quota_retries_on_429_then_succeeds():
    fn = MagicMock(side_effect=[_api_error_429(), _api_error_429(), "ok"])
    assert wgs._retry_on_quota(fn, max_tries=5, base_delay=0) == "ok"
    assert fn.call_count == 3


def test_retry_on_quota_gives_up_after_max_tries():
    fn = MagicMock(side_effect=_api_error_429())
    with pytest.raises(gspread.exceptions.APIError):
        wgs._retry_on_quota(fn, max_tries=3, base_delay=0)
    assert fn.call_count == 3


def test_retry_on_quota_reraises_non_429_immediately():
    fn = MagicMock(side_effect=_api_error_500())
    with pytest.raises(gspread.exceptions.APIError):
        wgs._retry_on_quota(fn, max_tries=5, base_delay=0)
    fn.assert_called_once()


# ---------------------------------------------------------------------------
# gc_login
# ---------------------------------------------------------------------------

@patch("writeGoogleSheet.gspread.authorize")
@patch("writeGoogleSheet.ServiceAccountCredentials.from_json_keyfile_dict")
@patch("writeGoogleSheet.get_secret", return_value={})
def test_gc_login_success_first_try(_get_secret, _creds, mock_authorize, fake_config):
    mock_authorize.return_value = "client"
    assert wgs.gc_login() == "client"


@patch("writeGoogleSheet.gspread.authorize")
@patch("writeGoogleSheet.ServiceAccountCredentials.from_json_keyfile_dict")
@patch("writeGoogleSheet.get_secret", return_value={})
def test_gc_login_retries_then_succeeds(_get_secret, mock_creds, mock_authorize, fake_config):
    mock_creds.side_effect = [Exception("boom"), Exception("boom"), MagicMock()]
    mock_authorize.return_value = "client"
    assert wgs.gc_login() == "client"
    assert mock_creds.call_count == 3


@patch("writeGoogleSheet.gspread.authorize")
@patch("writeGoogleSheet.ServiceAccountCredentials.from_json_keyfile_dict")
@patch("writeGoogleSheet.get_secret", return_value={})
def test_gc_login_exhausts_retries_returns_none(_get_secret, mock_creds, mock_authorize, fake_config):
    mock_creds.side_effect = Exception("boom")
    assert wgs.gc_login() is None
    assert mock_creds.call_count == fake_config["google"]["max_tries"]


# ---------------------------------------------------------------------------
# open_sheet
# ---------------------------------------------------------------------------

@patch("writeGoogleSheet.get_user_pwd", return_value=("user", "sheet-id"))
def test_open_sheet_with_named_sheet(mock_get_user_pwd):
    client = MagicMock()
    client.open_by_key.return_value.worksheet.return_value = "ws"
    result = wgs.open_sheet(client, "ws_id", "Sheet1")
    client.open_by_key.assert_called_once_with("sheet-id")
    client.open_by_key.return_value.worksheet.assert_called_once_with("Sheet1")
    assert result == "ws"


@patch("writeGoogleSheet.get_user_pwd", return_value=("user", "sheet-id"))
def test_open_sheet_default_sheet1(_mock):
    client = MagicMock()
    client.open_by_key.return_value.sheet1 = "first-sheet"
    result = wgs.open_sheet(client, "ws_id")
    assert result == "first-sheet"


@patch("writeGoogleSheet.get_user_pwd", return_value=("user", "sheet-id"))
def test_open_sheet_worksheet_not_found_returns_none(_mock):
    client = MagicMock()
    client.open_by_key.return_value.worksheet.side_effect = gspread.exceptions.WorksheetNotFound
    assert wgs.open_sheet(client, "ws_id", "Missing") is None


def _api_error():
    resp = MagicMock()
    resp.json.return_value = {"error": {"code": 500, "message": "boom", "status": "ERR"}}
    return gspread.exceptions.APIError(resp)


@patch("writeGoogleSheet.get_user_pwd", return_value=("user", "sheet-id"))
def test_open_sheet_api_error_then_success(_mock):
    client = MagicMock()
    ok_ws = MagicMock()
    client.open_by_key.return_value.worksheet.side_effect = [_api_error(), ok_ws]
    result = wgs.open_sheet(client, "ws_id", "Sheet1")
    assert result is ok_ws


@patch("writeGoogleSheet.get_user_pwd", return_value=("user", "sheet-id"))
def test_open_sheet_api_error_exhausted_returns_none(_mock):
    client = MagicMock()
    client.open_by_key.return_value.worksheet.side_effect = _api_error()
    assert wgs.open_sheet(client, "ws_id", "Sheet1") is None


@patch("writeGoogleSheet.get_user_pwd", return_value=("user", "sheet-id"))
def test_open_sheet_worksheet_not_found_during_retry_returns_none(_mock):
    client = MagicMock()
    client.open_by_key.return_value.worksheet.side_effect = [
        _api_error(), gspread.exceptions.WorksheetNotFound
    ]
    assert wgs.open_sheet(client, "ws_id", "Sheet1") is None


# ---------------------------------------------------------------------------
# open_workbook / open_worksheet
# ---------------------------------------------------------------------------

@patch("writeGoogleSheet.get_user_pwd", return_value=("user", "sheet-id"))
def test_open_workbook_passthrough(_mock):
    client = MagicMock()
    client.open_by_key.return_value = "wb"
    assert wgs.open_workbook(client, "ws_id") == "wb"
    client.open_by_key.assert_called_once_with("sheet-id")


def test_open_worksheet_found():
    wb = MagicMock()
    wb.worksheet.return_value = "ws"
    assert wgs.open_worksheet(wb, "Sheet1") == "ws"


def test_open_worksheet_default_sheet1():
    wb = MagicMock()
    wb.sheet1 = "first"
    assert wgs.open_worksheet(wb, None) == "first"


def test_open_worksheet_not_found_returns_none():
    wb = MagicMock()
    wb.worksheet.side_effect = gspread.exceptions.WorksheetNotFound
    assert wgs.open_worksheet(wb, "Missing") is None


# ---------------------------------------------------------------------------
# update_data
# ---------------------------------------------------------------------------

def _df():
    import pandas as pd
    return pd.DataFrame({"a": [1, 2], "b": [3, 4]})


def test_update_data_range_a1_clears_whole_sheet():
    ws = MagicMock()
    wgs.update_data(ws, _df(), "A1")
    ws.clear.assert_called_once()
    ws.batch_clear.assert_not_called()
    ws.update.assert_called_once_with(
        range_name="A1", values=[["a", "b"], [1, 3], [2, 4]]
    )


def test_update_data_other_range_batch_clears_and_adds_note():
    ws = MagicMock()
    wgs.update_data(ws, _df(), "A1:B10")
    ws.clear.assert_not_called()
    ws.batch_clear.assert_called_once_with(["A1:B10"])
    assert ws.update.call_count == 2
    note_call = ws.update.call_args_list[1]
    assert note_call.kwargs["range_name"] == "A16"
    assert ws.format.call_count == 2
