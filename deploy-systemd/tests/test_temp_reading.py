"""Tests for temperature reading functions."""

import subprocess
import unittest
from unittest.mock import mock_open, patch

from fan_control import read_cpu_temp, read_temp_sysfs, read_temp_vcgencmd


class TestReadTempVcgencmd(unittest.TestCase):
    """Tests for read_temp_vcgencmd function."""

    @patch("fan_control.os.path.exists")
    @patch("fan_control.subprocess.check_output")
    def test_success(self, mock_check_output, mock_exists):
        """Test successful temperature reading via vcgencmd."""
        mock_exists.return_value = True
        mock_check_output.return_value = b"temp=45.5'C\n"
        temp = read_temp_vcgencmd()
        self.assertEqual(temp, 45.5)

    @patch("fan_control.os.path.exists")
    @patch("fan_control.subprocess.check_output")
    def test_no_match(self, mock_check_output, mock_exists):
        """Test when vcgencmd output doesn't match expected format."""
        mock_exists.return_value = True
        mock_check_output.return_value = b"invalid output\n"
        temp = read_temp_vcgencmd()
        self.assertIsNone(temp)

    @patch("fan_control.os.path.exists")
    def test_command_not_found(self, mock_exists):
        """Test when vcgencmd command is not found."""
        mock_exists.return_value = False
        temp = read_temp_vcgencmd()
        self.assertIsNone(temp)

    @patch("fan_control.os.path.exists")
    @patch("fan_control.subprocess.check_output")
    def test_subprocess_error(self, mock_check_output, mock_exists):
        """Test subprocess error handling."""
        mock_exists.return_value = True
        mock_check_output.side_effect = subprocess.SubprocessError("Failed")
        temp = read_temp_vcgencmd()
        self.assertIsNone(temp)

    @patch("fan_control.os.path.exists")
    @patch("fan_control.subprocess.check_output")
    def test_value_error(self, mock_check_output, mock_exists):
        """Test value error handling."""
        mock_exists.return_value = True
        mock_check_output.return_value = b"temp=invalid'C\n"
        temp = read_temp_vcgencmd()
        self.assertIsNone(temp)


class TestReadTempSysfs(unittest.TestCase):
    """Tests for read_temp_sysfs function."""

    @patch("builtins.open", new_callable=mock_open, read_data="45500\n")
    def test_success(self, mock_file):
        """Test successful temperature reading via sysfs."""
        temp = read_temp_sysfs()
        self.assertEqual(temp, 45.5)
        mock_file.assert_called_once_with("/sys/class/thermal/thermal_zone0/temp", "r", encoding="utf-8")

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_file_not_found(self, mock_file):
        """Test when thermal zone file doesn't exist."""
        temp = read_temp_sysfs()
        self.assertIsNone(temp)

    @patch("builtins.open", side_effect=PermissionError)
    def test_permission_error(self, mock_file):
        """Test permission denied error."""
        temp = read_temp_sysfs()
        self.assertIsNone(temp)

    @patch("builtins.open", new_callable=mock_open, read_data="invalid\n")
    def test_invalid_data(self, mock_file):
        """Test when sysfs file contains invalid data."""
        temp = read_temp_sysfs()
        self.assertIsNone(temp)

    @patch("builtins.open", side_effect=IOError("Read error"))
    def test_io_error(self, mock_file):
        """Test general IO error handling."""
        temp = read_temp_sysfs()
        self.assertIsNone(temp)


class TestReadCpuTemp(unittest.TestCase):
    """Tests for read_cpu_temp function."""

    def test_simulated_temp(self):
        """Test simulated temperature mode."""
        temp = read_cpu_temp(simulate_temp=55.5)
        self.assertEqual(temp, 55.5)

    @patch("fan_control.read_temp_vcgencmd")
    def test_vcgencmd_success(self, mock_vcgencmd):
        """Test temperature reading via vcgencmd."""
        mock_vcgencmd.return_value = 50.0
        temp = read_cpu_temp()
        self.assertEqual(temp, 50.0)

    @patch("fan_control.read_temp_vcgencmd")
    @patch("fan_control.read_temp_sysfs")
    def test_fallback_to_sysfs(self, mock_sysfs, mock_vcgencmd):
        """Test fallback to sysfs when vcgencmd fails."""
        mock_vcgencmd.return_value = None
        mock_sysfs.return_value = 48.0
        temp = read_cpu_temp()
        self.assertEqual(temp, 48.0)

    @patch("fan_control.read_temp_vcgencmd")
    @patch("fan_control.read_temp_sysfs")
    def test_both_methods_fail(self, mock_sysfs, mock_vcgencmd):
        """Test when both vcgencmd and sysfs fail."""
        mock_vcgencmd.return_value = None
        mock_sysfs.return_value = None
        temp = read_cpu_temp()
        self.assertIsNone(temp)


if __name__ == "__main__":
    unittest.main()
