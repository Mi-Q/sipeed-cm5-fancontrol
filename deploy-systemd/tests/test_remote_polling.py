"""Tests for remote temperature polling functions."""

import subprocess
import unittest
from unittest.mock import patch

from fan_control import FanController, read_remote_temp_http, read_remote_temp_ssh


class TestReadRemoteTempSSH(unittest.TestCase):
    """Tests for read_remote_temp_ssh function."""

    @patch("fan_control.subprocess.check_output")
    def test_success(self, mock_check_output):
        """Test successful SSH temperature reading."""
        mock_check_output.return_value = b"temp=52.3'C\n"
        temp = read_remote_temp_ssh("pi@192.168.1.100", timeout=5)
        self.assertEqual(temp, 52.3)

    @patch("fan_control.subprocess.check_output")
    def test_timeout(self, mock_check_output):
        """Test SSH timeout handling."""
        mock_check_output.side_effect = subprocess.TimeoutExpired(cmd="ssh", timeout=5)
        temp = read_remote_temp_ssh("pi@192.168.1.100", timeout=5)
        self.assertIsNone(temp)

    @patch("fan_control.subprocess.check_output")
    def test_connection_error(self, mock_check_output):
        """Test SSH connection error."""
        mock_check_output.side_effect = subprocess.SubprocessError("Connection refused")
        temp = read_remote_temp_ssh("pi@192.168.1.100", timeout=5)
        self.assertIsNone(temp)

    @patch("fan_control.subprocess.check_output")
    def test_fallback_to_sysfs(self, mock_check_output):
        """Test fallback to sysfs when vcgencmd fails."""
        # First call (vcgencmd) fails, second call (sysfs) succeeds
        mock_check_output.side_effect = [
            subprocess.SubprocessError("vcgencmd not found"),
            b"48500\n",
        ]
        temp = read_remote_temp_ssh("pi@192.168.1.100", timeout=5)
        self.assertEqual(temp, 48.5)

    @patch("fan_control.subprocess.check_output")
    def test_both_methods_fail(self, mock_check_output):
        """Test when both vcgencmd and sysfs fail."""
        mock_check_output.side_effect = subprocess.SubprocessError("Failed")
        temp = read_remote_temp_ssh("pi@192.168.1.100", timeout=5)
        self.assertIsNone(temp)

    @patch("fan_control.subprocess.check_output")
    def test_sysfs_timeout_after_vcgencmd_fails(self, mock_check_output):
        """Test when vcgencmd fails and sysfs times out."""
        # First call (vcgencmd) fails, second call (sysfs) times out
        mock_check_output.side_effect = [
            subprocess.SubprocessError("vcgencmd not found"),
            subprocess.TimeoutExpired(cmd="ssh", timeout=5),
        ]
        temp = read_remote_temp_ssh("pi@192.168.1.100", timeout=5)
        self.assertIsNone(temp)

    @patch("fan_control.subprocess.check_output")
    def test_sysfs_subprocess_error_after_vcgencmd_fails(self, mock_check_output):
        """Test when vcgencmd fails with timeout and sysfs fails with subprocess error."""
        # First call (vcgencmd) times out, second call (sysfs) has subprocess error
        mock_check_output.side_effect = [
            subprocess.TimeoutExpired(cmd="ssh", timeout=5),
            subprocess.SubprocessError("Connection failed"),
        ]
        temp = read_remote_temp_ssh("pi@192.168.1.100", timeout=5)
        self.assertIsNone(temp)


class TestReadRemoteTempHTTP(unittest.TestCase):
    """Tests for read_remote_temp_http function."""

    @patch("fan_control.subprocess.check_output")
    def test_success(self, mock_check_output):
        """Test successful HTTP temperature reading."""
        mock_check_output.return_value = b"53.2"
        temp = read_remote_temp_http("http://192.168.1.100:2505/temp")
        self.assertEqual(temp, 53.2)

    @patch("fan_control.subprocess.check_output")
    def test_timeout(self, mock_check_output):
        """Test HTTP timeout handling."""
        mock_check_output.side_effect = subprocess.TimeoutExpired(cmd="curl", timeout=5)
        temp = read_remote_temp_http("http://192.168.1.100:2505/temp", timeout=5)
        self.assertIsNone(temp)

    @patch("fan_control.subprocess.check_output")
    def test_connection_error(self, mock_check_output):
        """Test HTTP connection error."""
        mock_check_output.side_effect = subprocess.SubprocessError("Connection refused")
        temp = read_remote_temp_http("http://192.168.1.100:2505/temp")
        self.assertIsNone(temp)

    @patch("fan_control.subprocess.check_output")
    def test_invalid_response(self, mock_check_output):
        """Test when HTTP returns non-numeric response."""
        mock_check_output.return_value = b"not a number"
        temp = read_remote_temp_http("http://192.168.1.100:2505/temp")
        self.assertIsNone(temp)

    @patch("fan_control.subprocess.check_output")
    def test_empty_response(self, mock_check_output):
        """Test when HTTP returns empty response."""
        mock_check_output.return_value = b""
        temp = read_remote_temp_http("http://192.168.1.100:2505/temp")
        self.assertIsNone(temp)

    @patch("fan_control.subprocess.check_output")
    def test_custom_timeout(self, mock_check_output):
        """Test custom timeout value."""
        mock_check_output.return_value = b"49.8"
        temp = read_remote_temp_http("http://192.168.1.100:2505/temp", timeout=15)
        self.assertEqual(temp, 49.8)


class TestRemotePeerPolling(unittest.TestCase):
    """Tests for parallel remote peer polling with ThreadPoolExecutor."""

    @patch("fan_control.read_cpu_temp")
    @patch("fan_control.read_remote_temp_http")
    def test_parallel_peer_polling_http(self, mock_http, mock_local):
        """Test parallel polling of multiple HTTP peers."""
        mock_local.return_value = 50.0

        # Use a side_effect function that returns different values based on URL
        def http_side_effect(url, timeout=5):
            if "peer1" in url:
                return 55.0
            elif "peer2" in url:
                return None
            elif "peer3" in url:
                return 52.0
            return None

        mock_http.side_effect = http_side_effect

        controller = FanController(pin=13, freq=50, poll=5, dry_run=True)
        controller.peers = [
            "http://peer1:2505/temp",
            "http://peer2:2505/temp",
            "http://peer3:2505/temp",
        ]
        controller.remote_method = "http"
        controller.aggregate = "avg"  # Use average aggregation
        controller.start()

        result = controller.run_once()
        self.assertIsNotNone(result)
        # Should have local + 3 peers (2 successful, 1 failed)
        self.assertIn("local", result["per_host"])
        self.assertEqual(result["per_host"]["local"], 50.0)
        self.assertEqual(result["per_host"]["http://peer1:2505/temp"], 55.0)
        self.assertIsNone(result["per_host"]["http://peer2:2505/temp"])
        self.assertEqual(result["per_host"]["http://peer3:2505/temp"], 52.0)
        # Aggregate should use valid temps only (50, 55, 52) = avg 52.333
        self.assertAlmostEqual(result["aggregated_temp"], 52.333, places=2)

    @patch("fan_control.read_cpu_temp")
    @patch("fan_control.read_remote_temp_ssh")
    def test_parallel_peer_polling_ssh(self, mock_ssh, mock_local):
        """Test parallel polling of multiple SSH peers."""
        mock_local.return_value = 48.0

        # Use a side_effect function for consistent results
        def ssh_side_effect(host, timeout=5):
            if "host1" in host:
                return 51.0
            elif "host2" in host:
                return 49.5
            return None

        mock_ssh.side_effect = ssh_side_effect

        controller = FanController(pin=13, freq=50, poll=5, dry_run=True)
        controller.peers = ["pi@host1", "pi@host2"]
        controller.remote_method = "ssh"
        controller.aggregate = "avg"  # Use average aggregation
        controller.start()

        result = controller.run_once()
        self.assertIsNotNone(result)
        self.assertEqual(len(result["per_host"]), 3)
        # Average of 48.0, 51.0, 49.5 = 49.5
        self.assertAlmostEqual(result["aggregated_temp"], 49.5, places=1)

    @patch("fan_control.read_cpu_temp")
    @patch("fan_control.read_remote_temp_http")
    def test_peer_polling_with_exceptions(self, mock_http, mock_local):
        """Test that exceptions in peer polling are handled gracefully."""
        mock_local.return_value = 50.0
        # Simulate various exceptions
        mock_http.side_effect = [
            55.0,
            OSError("Connection failed"),
            ValueError("Invalid value"),
            subprocess.SubprocessError("Subprocess failed"),
        ]

        controller = FanController(pin=13, freq=50, poll=5, dry_run=True)
        controller.peers = [
            "http://peer1:2505/temp",
            "http://peer2:2505/temp",
            "http://peer3:2505/temp",
            "http://peer4:2505/temp",
        ]
        controller.remote_method = "http"
        controller.start()

        with patch("fan_control.logger") as mock_logger:
            result = controller.run_once()
            # Should still succeed with local + peer1
            self.assertIsNotNone(result)
            # Should log debug messages for errors
            self.assertGreaterEqual(mock_logger.debug.call_count, 3)


if __name__ == "__main__":
    unittest.main()
