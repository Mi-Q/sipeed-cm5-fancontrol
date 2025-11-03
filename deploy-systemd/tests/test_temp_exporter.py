"""Tests for temperature exporter HTTP server."""

import subprocess
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

from temp_exporter import (
    TempHandler,
    main,
    read_cpu_temp,
    read_temp_sysfs,
    read_temp_vcgencmd,
)


class TestReadTempVcgencmdExporter(unittest.TestCase):
    """Tests for read_temp_vcgencmd in exporter."""

    @patch("temp_exporter.os.path.exists")
    @patch("temp_exporter.subprocess.check_output")
    def test_success(self, mock_check_output, mock_exists):
        """Test successful temperature reading."""
        mock_exists.return_value = True
        mock_check_output.return_value = b"temp=51.2'C\n"
        temp = read_temp_vcgencmd()
        self.assertEqual(temp, 51.2)

    @patch("temp_exporter.os.path.exists")
    def test_file_not_found(self, mock_exists):
        """Test when vcgencmd doesn't exist."""
        mock_exists.return_value = False
        temp = read_temp_vcgencmd()
        self.assertIsNone(temp)

    @patch("temp_exporter.os.path.exists")
    @patch("temp_exporter.subprocess.check_output")
    def test_subprocess_error_debug_logging(self, mock_check_output, mock_exists):
        """Test debug logging when vcgencmd subprocess fails."""
        mock_exists.return_value = True
        mock_check_output.side_effect = subprocess.SubprocessError("Command failed")

        with patch("temp_exporter.logger") as mock_logger:
            temp = read_temp_vcgencmd()
            self.assertIsNone(temp)
            # Should log debug message
            mock_logger.debug.assert_called_once()
            self.assertIn("vcgencmd failed", mock_logger.debug.call_args[0][0])


class TestReadTempSysfsExporter(unittest.TestCase):
    """Tests for read_temp_sysfs in exporter."""

    @patch("builtins.open", create=True)
    def test_success(self, mock_open_file):
        """Test successful sysfs reading."""
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = "47800"
        mock_open_file.return_value = mock_file
        temp = read_temp_sysfs()
        self.assertEqual(temp, 47.8)

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_file_not_found(self, mock_open_file):
        """Test when file doesn't exist."""
        temp = read_temp_sysfs()
        self.assertIsNone(temp)


class TestReadCpuTempExporter(unittest.TestCase):
    """Tests for read_cpu_temp in exporter."""

    @patch("temp_exporter.read_temp_vcgencmd")
    def test_vcgencmd_success(self, mock_vcgencmd):
        """Test temperature reading via vcgencmd."""
        mock_vcgencmd.return_value = 49.5
        temp = read_cpu_temp()
        self.assertEqual(temp, 49.5)

    @patch("temp_exporter.read_temp_vcgencmd")
    @patch("temp_exporter.read_temp_sysfs")
    def test_fallback_to_sysfs(self, mock_sysfs, mock_vcgencmd):
        """Test fallback to sysfs."""
        mock_vcgencmd.return_value = None
        mock_sysfs.return_value = 48.3
        temp = read_cpu_temp()
        self.assertEqual(temp, 48.3)


class TestTempHandler(unittest.TestCase):
    """Tests for TempHandler HTTP request handler."""

    @patch("temp_exporter.read_cpu_temp")
    def test_temp_endpoint_success(self, mock_read_temp):
        """Test /temp endpoint with successful temperature reading."""
        mock_read_temp.return_value = 52.7

        # Create handler with mocked components
        handler = TempHandler.__new__(TempHandler)
        handler.wfile = BytesIO()
        handler.path = "/temp"
        handler.request_version = "HTTP/1.1"

        # Mock the response methods
        with (
            patch.object(handler, "send_response") as mock_send_response,
            patch.object(handler, "send_header"),
            patch.object(handler, "end_headers") as mock_end_headers,
        ):

            handler.do_GET()

            mock_send_response.assert_called_once_with(200)
            mock_end_headers.assert_called_once()

            # Check response contains the temperature
            response_data = handler.wfile.getvalue().decode()
            self.assertIn("52.7", response_data)

    @patch("temp_exporter.read_cpu_temp")
    def test_temp_endpoint_failure(self, mock_read_temp):
        """Test /temp endpoint when temperature reading fails."""
        mock_read_temp.return_value = None

        handler = TempHandler.__new__(TempHandler)
        handler.wfile = BytesIO()
        handler.path = "/temp"
        handler.request_version = "HTTP/1.1"

        with (
            patch.object(handler, "send_response") as mock_send_response,
            patch.object(handler, "send_header"),
            patch.object(handler, "end_headers"),
        ):

            handler.do_GET()

            mock_send_response.assert_called_once_with(500)

    @patch("temp_exporter.read_cpu_temp")
    def test_metrics_endpoint_success(self, mock_read_temp):
        """Test /metrics endpoint with successful reading."""
        mock_read_temp.return_value = 54.3

        handler = TempHandler.__new__(TempHandler)
        handler.wfile = BytesIO()
        handler.path = "/metrics"
        handler.request_version = "HTTP/1.1"

        with (
            patch.object(handler, "send_response") as mock_send_response,
            patch.object(handler, "send_header"),
            patch.object(handler, "end_headers") as mock_end_headers,
        ):

            handler.do_GET()

            mock_send_response.assert_called_once_with(200)
            mock_end_headers.assert_called_once()

            response_data = handler.wfile.getvalue().decode()
            self.assertIn("node_temperature_celsius", response_data)
            self.assertIn("54.3", response_data)

    @patch("temp_exporter.read_cpu_temp")
    def test_metrics_endpoint_failure(self, mock_read_temp):
        """Test /metrics endpoint when reading fails."""
        mock_read_temp.return_value = None

        handler = TempHandler.__new__(TempHandler)
        handler.wfile = BytesIO()
        handler.path = "/metrics"
        handler.request_version = "HTTP/1.1"

        with (
            patch.object(handler, "send_response") as mock_send_response,
            patch.object(handler, "end_headers"),
            patch.object(handler, "send_header"),
        ):

            handler.do_GET()

            mock_send_response.assert_called_once_with(200)

    def test_invalid_endpoint(self):
        """Test invalid endpoint returns 404."""
        handler = TempHandler.__new__(TempHandler)
        handler.wfile = BytesIO()
        handler.path = "/invalid"
        handler.request_version = "HTTP/1.1"

        with patch.object(handler, "send_response") as mock_send_response, patch.object(handler, "end_headers"):

            handler.do_GET()

            mock_send_response.assert_called_once_with(404)

    def test_log_message_suppression(self):
        """Test that log_message is properly overridden."""
        handler = TempHandler.__new__(TempHandler)
        handler.client_address = ("127.0.0.1", 12345)
        # Should not raise an exception
        handler.log_message("test %s", "message")


class TestMainFunction(unittest.TestCase):
    """Tests for main function and argument parsing."""

    @patch("temp_exporter.socketserver.TCPServer")
    @patch("sys.argv", ["temp_exporter.py"])
    def test_main_default_args(self, mock_server):
        """Test main function with default arguments."""
        mock_httpd = MagicMock()
        mock_server.return_value.__enter__.return_value = mock_httpd
        # Make serve_forever raise KeyboardInterrupt to exit cleanly
        mock_httpd.serve_forever.side_effect = KeyboardInterrupt()

        with patch("temp_exporter.logger") as mock_logger:
            main()

            # Should create server with default bind and port
            mock_server.assert_called_once_with(("0.0.0.0", 2505), TempHandler)
            # Should log startup message
            mock_logger.info.assert_any_call("Temperature exporter listening on %s:%d", "0.0.0.0", 2505)
            # Should log shutdown on KeyboardInterrupt
            mock_logger.info.assert_any_call("Shutting down")

    @patch("temp_exporter.socketserver.TCPServer")
    @patch("sys.argv", ["temp_exporter.py", "--bind", "127.0.0.1", "--port", "9090"])
    def test_main_custom_args(self, mock_server):
        """Test main function with custom bind address and port."""
        mock_httpd = MagicMock()
        mock_server.return_value.__enter__.return_value = mock_httpd
        mock_httpd.serve_forever.side_effect = KeyboardInterrupt()

        main()

        # Should create server with custom bind and port
        mock_server.assert_called_once_with(("127.0.0.1", 9090), TempHandler)

    @patch("temp_exporter.socketserver.TCPServer")
    @patch("temp_exporter.logger")
    @patch("sys.argv", ["temp_exporter.py", "--verbose"])
    def test_main_verbose_mode(self, mock_logger, mock_server):
        """Test main function with verbose logging enabled."""
        mock_httpd = MagicMock()
        mock_server.return_value.__enter__.return_value = mock_httpd
        mock_httpd.serve_forever.side_effect = KeyboardInterrupt()

        main()

        # Should set logger level to DEBUG
        mock_logger.setLevel.assert_called_once()

    @patch("temp_exporter.socketserver.TCPServer")
    @patch("sys.argv", ["temp_exporter.py"])
    def test_main_serve_forever(self, mock_server):
        """Test that main function calls serve_forever."""
        mock_httpd = MagicMock()
        mock_server.return_value.__enter__.return_value = mock_httpd
        mock_httpd.serve_forever.side_effect = KeyboardInterrupt()

        main()

        # Should call serve_forever
        mock_httpd.serve_forever.assert_called_once()


if __name__ == "__main__":
    unittest.main()
