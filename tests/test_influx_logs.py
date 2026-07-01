import json
from unittest.mock import MagicMock, patch

import influxdb_client
import pytest

import writeGoogleSheet as wgs


# ---------------------------------------------------------------------------
# db_connect
# ---------------------------------------------------------------------------

@patch("writeGoogleSheet.influxdb_client.InfluxDBClient")
def test_db_connect_success(mock_client_cls):
    mock_client_cls.return_value = "client"
    assert wgs.db_connect("url", "token", "org") == "client"


@patch("writeGoogleSheet.influxdb_client.InfluxDBClient")
def test_db_connect_error_exits(mock_client_cls):
    mock_client_cls.side_effect = influxdb_client.client.exceptions.InfluxDBError(
        response=MagicMock(status=500, data='{"message": "boom"}')
    )
    with pytest.raises(SystemExit):
        wgs.db_connect("url", "token", "org")


# ---------------------------------------------------------------------------
# _parse_message_content
# ---------------------------------------------------------------------------

def test_parse_message_content_json_list():
    assert wgs._parse_message_content('[{"a": 1}]') == [{"a": 1}]


def test_parse_message_content_json_dict():
    assert wgs._parse_message_content('{"a": 1}') == {"a": 1}


def test_parse_message_content_malformed_json_returns_raw():
    raw = "{not valid json"
    assert wgs._parse_message_content(raw) == raw


def test_parse_message_content_non_string_passthrough():
    assert wgs._parse_message_content(42) == 42


# ---------------------------------------------------------------------------
# _extract_log_details
# ---------------------------------------------------------------------------

def test_extract_log_details_basic_header():
    msg = [{"module": "mod-a", "severity": "INFO"}]
    rec = {}
    severity, module, text = wgs._extract_log_details(msg, rec)
    assert severity == "INFO"
    assert module == "mod-a"
    # msg[0] has no "message" key -> _msg defaults to ""
    assert text == ""


def test_extract_log_details_source_location_with_line():
    msg = [{"module": "mod-a", "severity": "INFO"}]
    rec = {"sourceLocation": {"file": "app.py", "line": 42}}
    severity, module, _text = wgs._extract_log_details(msg, rec)
    assert module == "app.py"
    assert severity == "INFO"


def test_extract_log_details_nested_message_dict_severity_from_msg():
    msg = [{"message": {"severity": "ERROR", "module": "inner", "message": "hello ", "event": "world"}}]
    rec = {}
    severity, module, text = wgs._extract_log_details(msg, rec)
    assert severity == "ERROR"
    assert "inner" in module
    assert text == "hello world"


def test_extract_log_details_error_keyword_forces_severity():
    msg = [{"message": {"module": "inner", "message": "Error happened", "event": ""}}]
    rec = {}
    severity, _module, _text = wgs._extract_log_details(msg, rec)
    assert severity == "ERROR"


def test_extract_log_details_exception_path_falls_back_to_msg():
    msg = "not a list"
    rec = {}
    severity, module, text = wgs._extract_log_details(msg, rec)
    assert text == msg
    assert severity == ""
    assert module == ""


def test_extract_log_details_typeerror_in_concat_falls_back_to_msg():
    # message is an int, so `_msg.get('message', "") + _msg.get('event', "")`
    # raises TypeError (int + str), exercising the except branch.
    msg = [{"message": {"message": 123, "event": "e"}}]
    rec = {}
    severity, _module, text = wgs._extract_log_details(msg, rec)
    assert text == msg
    assert severity == ""


# ---------------------------------------------------------------------------
# _process_log_record
# ---------------------------------------------------------------------------

def _record(value):
    rec = MagicMock()
    rec.get_value.return_value = value
    return rec


def test_process_log_record_bad_json_returns_empty():
    assert wgs._process_log_record(_record("not json")) == []


def test_process_log_record_wrong_view_mode_returns_empty():
    payload = json.dumps({"labels": {"viewMode": "Other"}, "jsonPayload": {"message": "hi"}})
    assert wgs._process_log_record(_record(payload)) == []


def test_process_log_record_skips_running_the_code_for():
    payload = json.dumps({
        "labels": {"viewMode": "Site"},
        "jsonPayload": {"message": "Running the code for something"},
        "timestamp": "t1",
    })
    assert wgs._process_log_record(_record(payload)) == []


def test_process_log_record_builds_row():
    payload = json.dumps({
        "labels": {"viewMode": "Site"},
        "jsonPayload": {"message": "plain message"},
        "timestamp": "t1",
    })
    rows = wgs._process_log_record(_record(payload))
    assert len(rows) == 1
    assert rows[0][0] == "t1"
    assert rows[0][3] == "plain message"


def test_process_log_record_truncates_long_message():
    long_msg = "x" * 1000
    payload = json.dumps({
        "labels": {"viewMode": "Site"},
        "jsonPayload": {"message": long_msg},
        "timestamp": "t1",
    })
    rows = wgs._process_log_record(_record(payload))
    assert len(rows[0][3]) == 512


# ---------------------------------------------------------------------------
# upd_logs_google_sheet
# ---------------------------------------------------------------------------

@patch("writeGoogleSheet.open_sheet", return_value=None)
@patch("writeGoogleSheet.db_connect")
@patch("writeGoogleSheet.get_secret")
def test_upd_logs_no_sheet_returns_early(mock_secret, mock_connect, _open_sheet):
    mock_secret.return_value = {"bucket": "b", "token": "t", "org": "o", "url": "u"}
    mock_connect.return_value.query_api.return_value.query.return_value = []
    wgs.upd_logs_google_sheet(MagicMock(), 7)


@patch("writeGoogleSheet.open_sheet")
@patch("writeGoogleSheet.db_connect")
@patch("writeGoogleSheet.get_secret")
def test_upd_logs_happy_path_writes_header_and_rows(mock_secret, mock_connect, mock_open_sheet):
    mock_secret.return_value = {"bucket": "b", "token": "t", "org": "o", "url": "u"}

    payload = json.dumps({
        "labels": {"viewMode": "Site"},
        "jsonPayload": {"message": "hello"},
        "timestamp": "t1",
    })
    record = _record(payload)
    table = MagicMock()
    table.records = [record]
    mock_connect.return_value.query_api.return_value.query.return_value = [table]

    ws = MagicMock()
    mock_open_sheet.return_value = ws

    wgs.upd_logs_google_sheet(MagicMock(), 7)

    ws.clear.assert_called_once()
    ws.update.assert_called_once()
    values = ws.update.call_args.kwargs["values"]
    assert values[0] == ["timestamp", "severity", "module", "msg"]
    assert values[1][0] == "t1"
