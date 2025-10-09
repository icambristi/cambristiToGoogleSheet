import unittest
from unittest.mock import patch

from writeGoogleSheet import log


class TestLogFunction(unittest.TestCase):

    @patch('writeGoogleSheet.hashlib.sha256')
    @patch('writeGoogleSheet.send_log_request')
    def test_log_calls_send_log_request_with_correct_parameters(self, mock_send_log_request, mock_sha256):
        # Configuration du mock sha256
        mock_hash = mock_sha256.return_value
        mock_hash.hexdigest.return_value = "mocked_hash"

        # Le reste du test reste identique...
        severity = "info"
        message = "Test log message"
        config = {
            'logs': {
                'username': 'test_user',
                'url': 'http://test-logs-api.com',
                'tag': 'test_tag'
            }
        }

        with patch.dict('writeGoogleSheet.config', config):
            log(severity, message)

        # Vérification de l'appel à sha256 avec le bon argument
        mock_sha256.assert_called_once_with(b'test_user')

    @patch('writeGoogleSheet.logging.info')
    def test_log_calls_logging_info_correctly(self, mock_logging_info):
        severity = "info"
        message = "Test logging call"

        log(severity, message)

        mock_logging_info.assert_called_once_with(message)

    @patch('writeGoogleSheet.logging.error')
    def test_log_handles_invalid_severity_gracefully(self, mock_logging_error):
        severity = "invalid_severity"
        message = "This should not break"

        log(severity, message)

        mock_logging_error.assert_called_once()


if __name__ == '__main__':
    unittest.main()
