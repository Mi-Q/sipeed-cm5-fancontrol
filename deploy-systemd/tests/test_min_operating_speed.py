"""Tests for minimum operating speed threshold to avoid fan dead zone."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fan_control import FanController


class TestMinOperatingSpeed(unittest.TestCase):
    """Tests for minimum operating speed functionality."""

    def setUp(self):
        """Set up test configuration."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_config.conf"

    def test_duty_above_minimum_unchanged(self):
        """Test that duty above minimum operating speed is not modified."""
        self.config_file.write_text(
            """
MODE=auto
TEMP_LOW=20
TEMP_HIGH=70
FAN_SPEED_LOW=0
FAN_SPEED_HIGH=100
FAN_CURVE=linear
FAN_MIN_OPERATING_SPEED=10
FAN_STOP_TEMP=20
"""
        )

        controller = FanController(dry_run=True, config_path=str(self.config_file))
        controller.start()

        # Test duties above minimum
        self.assertEqual(controller._apply_min_operating_speed(50.0, 40.0), 50.0)
        self.assertEqual(controller._apply_min_operating_speed(20.0, 30.0), 20.0)
        self.assertEqual(controller._apply_min_operating_speed(10.0, 25.0), 10.0)

    def test_duty_in_dead_zone_snaps_to_minimum(self):
        """Test that duty in dead zone snaps to minimum operating speed."""
        self.config_file.write_text(
            """
MODE=auto
TEMP_LOW=20
TEMP_HIGH=70
FAN_SPEED_LOW=0
FAN_MIN_OPERATING_SPEED=10
FAN_STOP_TEMP=20
"""
        )

        controller = FanController(dry_run=True, config_path=str(self.config_file))
        controller.start()

        # Duty in dead zone with temp above stop temp should snap to minimum
        self.assertEqual(controller._apply_min_operating_speed(5.0, 25.0), 10.0)
        self.assertEqual(controller._apply_min_operating_speed(8.0, 30.0), 10.0)
        self.assertEqual(controller._apply_min_operating_speed(1.0, 21.0), 10.0)

    def test_duty_below_stop_temp_stays_zero(self):
        """Test that fan stays off when temperature is at or below stop temp."""
        self.config_file.write_text(
            """
MODE=auto
FAN_MIN_OPERATING_SPEED=10
FAN_STOP_TEMP=20
"""
        )

        controller = FanController(dry_run=True, config_path=str(self.config_file))
        controller.start()

        # Even with duty in dead zone, stay off if temp <= stop_temp
        self.assertEqual(controller._apply_min_operating_speed(5.0, 20.0), 0.0)
        self.assertEqual(controller._apply_min_operating_speed(8.0, 18.0), 0.0)
        self.assertEqual(controller._apply_min_operating_speed(1.0, 15.0), 0.0)

    def test_zero_duty_stays_zero(self):
        """Test that zero duty remains zero regardless of temperature."""
        self.config_file.write_text(
            """
MODE=auto
FAN_MIN_OPERATING_SPEED=10
FAN_STOP_TEMP=20
"""
        )

        controller = FanController(dry_run=True, config_path=str(self.config_file))
        controller.start()

        # Zero duty stays zero
        self.assertEqual(controller._apply_min_operating_speed(0.0, 15.0), 0.0)
        self.assertEqual(controller._apply_min_operating_speed(0.0, 25.0), 0.0)
        self.assertEqual(controller._apply_min_operating_speed(0.0, 50.0), 0.0)


class TestMinOperatingSpeedIntegration(unittest.TestCase):
    """Integration tests with full temperature-to-duty calculation."""

    def setUp(self):
        """Set up test configuration."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_config.conf"

    @patch("fan_control.read_cpu_temp")
    def test_exponential_curve_with_min_speed(self, mock_read_temp):
        """Test exponential curve applies minimum operating speed correctly."""
        self.config_file.write_text(
            """
MODE=auto
TEMP_LOW=30
TEMP_HIGH=70
FAN_SPEED_LOW=0
FAN_SPEED_HIGH=100
FAN_CURVE=exponential
FAN_MIN_OPERATING_SPEED=10
FAN_STOP_TEMP=20
"""
        )

        controller = FanController(dry_run=True, config_path=str(self.config_file))
        controller.start()

        # Below stop temp - should be 0
        mock_read_temp.return_value = 18.0
        result = controller.run_once()
        self.assertEqual(result["duty"], 0.0)

        # Just above stop temp - exponential would give ~1.5%, should snap to 10%
        mock_read_temp.return_value = 35.0
        result = controller.run_once()
        self.assertEqual(result["duty"], 10.0)

        # Higher temp - exponential ~6.25%, should snap to 10%
        mock_read_temp.return_value = 40.0
        result = controller.run_once()
        self.assertEqual(result["duty"], 10.0)

        # Even higher - exponential ~25%, should stay at calculated value
        mock_read_temp.return_value = 50.0
        result = controller.run_once()
        self.assertAlmostEqual(result["duty"], 25.0, places=1)

    @patch("fan_control.read_cpu_temp")
    def test_linear_curve_with_min_speed(self, mock_read_temp):
        """Test linear curve applies minimum operating speed correctly."""
        self.config_file.write_text(
            """
MODE=auto
TEMP_LOW=30
TEMP_HIGH=70
FAN_SPEED_LOW=0
FAN_SPEED_HIGH=100
FAN_CURVE=linear
FAN_MIN_OPERATING_SPEED=10
FAN_STOP_TEMP=20
"""
        )

        controller = FanController(dry_run=True, config_path=str(self.config_file))
        controller.start()

        # Below stop temp - should be 0
        mock_read_temp.return_value = 15.0
        result = controller.run_once()
        self.assertEqual(result["duty"], 0.0)

        # At stop temp - should be 0
        mock_read_temp.return_value = 20.0
        result = controller.run_once()
        self.assertEqual(result["duty"], 0.0)

        # Just above stop temp, linear would give 2.5%, should snap to 10%
        mock_read_temp.return_value = 31.0
        result = controller.run_once()
        self.assertEqual(result["duty"], 10.0)

        # Higher temp - linear ~12.5%, should stay at calculated value
        mock_read_temp.return_value = 35.0
        result = controller.run_once()
        self.assertAlmostEqual(result["duty"], 12.5, places=1)

    @patch("fan_control.read_cpu_temp")
    def test_step_curve_with_min_speed(self, mock_read_temp):
        """Test step curve with minimum operating speed."""
        self.config_file.write_text(
            """
MODE=auto
TEMP_LOW=10
TEMP_HIGH=80
FAN_SPEED_LOW=0
FAN_SPEED_HIGH=100
FAN_CURVE=step
STEP_ZONES=20:0,30:5,40:15,50:30
FAN_MIN_OPERATING_SPEED=10
FAN_STOP_TEMP=18
"""
        )

        controller = FanController(dry_run=True, config_path=str(self.config_file))
        controller.start()

        # Below stop temp and first zone - should be 0
        mock_read_temp.return_value = 15.0
        result = controller.run_once()
        self.assertEqual(result["duty"], 0.0)

        # In second zone (30-40°C) configured at 5% - should snap to 10%
        mock_read_temp.return_value = 35.0
        result = controller.run_once()
        self.assertEqual(result["duty"], 10.0)

        # In third zone (40-50°C) configured at 15% - above minimum, stays 15%
        mock_read_temp.return_value = 45.0
        result = controller.run_once()
        self.assertEqual(result["duty"], 15.0)


class TestConfigDefaults(unittest.TestCase):
    """Test default values for minimum operating speed settings."""

    def test_defaults_when_config_missing(self):
        """Test that defaults are used when config file is missing."""
        controller = FanController(dry_run=True, config_path="/nonexistent/config.conf")
        self.assertEqual(controller.fan_min_operating_speed, 30.0)
        self.assertEqual(controller.fan_stop_temp, 0.0)

    def test_defaults_when_values_not_in_config(self):
        """Test defaults are used when values are not specified in config."""
        temp_dir = tempfile.mkdtemp()
        config_file = Path(temp_dir) / "test_config.conf"
        config_file.write_text("MODE=auto\n")

        controller = FanController(dry_run=True, config_path=str(config_file))
        self.assertEqual(controller.fan_min_operating_speed, 30.0)
        self.assertEqual(controller.fan_stop_temp, 0.0)


if __name__ == "__main__":
    unittest.main()
