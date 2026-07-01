import builtins
from unittest.mock import mock_open, patch

import writeGoogleSheet


def test_load_config_prefers_app_path():
    yaml_text = "google:\n  max_tries: 5\n"
    m = mock_open(read_data=yaml_text)
    with patch("builtins.open", m):
        result = writeGoogleSheet.load_config()
    m.assert_any_call("/app/config.yml")
    assert result == {"google": {"max_tries": 5}}


def test_load_config_falls_back_to_local_path():
    yaml_text = "google:\n  max_tries: 2\n"
    real_open = builtins.open

    def side_effect(path, *a, **kw):
        if path == "/app/config.yml":
            raise FileNotFoundError
        if path == "config.yml":
            return mock_open(read_data=yaml_text)(*a, **kw)
        return real_open(path, *a, **kw)

    with patch("builtins.open", side_effect=side_effect):
        result = writeGoogleSheet.load_config()
    assert result == {"google": {"max_tries": 2}}
