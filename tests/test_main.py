"""Exercise the `if __name__ == '__main__':` block directly.

We exec just that source block against writeGoogleSheet's own module
namespace (with gc_login / upd_* / threading.Thread mocked out), instead of
re-importing the whole file, so real network/Google/InfluxDB calls never
happen.
"""
import sys
from unittest.mock import MagicMock

import pytest

import writeGoogleSheet as wgs


def _exec_main_block():
    with open(wgs.__file__) as f:
        source = f.read()
    marker = "if __name__ == '__main__':"
    idx = source.index(marker)
    # pad with blank lines so line numbers still match the real file,
    # which keeps coverage.py's line tracking accurate for this block.
    padded = "\n" * source[:idx].count("\n") + source[idx:]
    code = compile(padded, wgs.__file__, "exec")
    g = vars(wgs)
    saved_name = g.get("__name__")
    g["__name__"] = "__main__"
    try:
        exec(code, g)
    finally:
        g["__name__"] = saved_name


class FakeThread:
    def __init__(self, target=None, args=()):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)

    def join(self):
        pass


@pytest.fixture
def main_mocks(monkeypatch, fake_config):
    monkeypatch.setattr(wgs, "gc_login", MagicMock(return_value="fake_gc"))
    monkeypatch.setattr(wgs.threading, "Thread", FakeThread)
    mocks = {
        "members": MagicMock(),
        "plans": MagicMock(),
        "logs": MagicMock(),
        "activities": MagicMock(),
    }
    monkeypatch.setattr(wgs, "upd_members_db_to_google_sheet", mocks["members"])
    monkeypatch.setattr(wgs, "upd_members_plans_to_google_sheet", mocks["plans"])
    monkeypatch.setattr(wgs, "upd_logs_google_sheet", mocks["logs"])
    monkeypatch.setattr(wgs, "upd_activities_to_google_sheet", mocks["activities"])
    return mocks


def test_main_no_args_runs_all_four_tasks(monkeypatch, main_mocks):
    monkeypatch.setattr(sys, "argv", ["writeGoogleSheet.py"])
    _exec_main_block()
    main_mocks["members"].assert_called_once()
    main_mocks["plans"].assert_called_once()
    main_mocks["logs"].assert_called_once()
    main_mocks["activities"].assert_called_once()


def test_main_geomap_flag_forces_members_only(monkeypatch, main_mocks):
    monkeypatch.setattr(sys, "argv", ["writeGoogleSheet.py", "-g"])
    _exec_main_block()
    main_mocks["members"].assert_called_once_with("fake_gc", True)
    main_mocks["plans"].assert_not_called()
    main_mocks["logs"].assert_not_called()
    main_mocks["activities"].assert_not_called()


def test_main_test_flag_sets_test_mode(monkeypatch, main_mocks):
    monkeypatch.setattr(sys, "argv", ["writeGoogleSheet.py", "-t", "-m"])
    _exec_main_block()
    assert wgs.test_mode is True


def test_main_days_flag_overrides_config(monkeypatch, main_mocks):
    monkeypatch.setattr(sys, "argv", ["writeGoogleSheet.py", "-l", "-d", "5"])
    _exec_main_block()
    main_mocks["logs"].assert_called_once_with("fake_gc", 5)


def test_main_days_falls_back_to_config_value(monkeypatch, main_mocks, fake_config):
    fake_config["logs"]["days"] = 21
    monkeypatch.setattr(sys, "argv", ["writeGoogleSheet.py", "-l"])
    _exec_main_block()
    main_mocks["logs"].assert_called_once_with("fake_gc", 21)


def test_main_days_defaults_to_seven_without_config(monkeypatch, main_mocks, fake_config):
    del fake_config["logs"]
    monkeypatch.setattr(sys, "argv", ["writeGoogleSheet.py", "-l"])
    _exec_main_block()
    main_mocks["logs"].assert_called_once_with("fake_gc", 7)
