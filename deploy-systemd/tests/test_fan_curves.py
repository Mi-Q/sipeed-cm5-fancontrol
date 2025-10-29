"""Tests for fan curve functionality including step curves with hysteresis."""

import tempfile
import unittest
from pathlib import Path

from fan_control import FanController, load_config


class TestStepCurveConfiguration(unittest.TestCase):
    """Tests for step curve configuration and parsing."""

    def test_parse_step_zones_valid(self):
        """Test parsing valid step zone configuration."""
        controller = FanController(dry_run=True)
        zones = controller._parse_step_zones("35:0,45:30,55:60,65:100")
        expected = [(35.0, 0.0), (45.0, 30.0), (55.0, 60.0), (65.0, 100.0)]
        self.assertEqual(zones, expected)

    def test_parse_step_zones_unsorted(self):
        """Test that step zones are sorted by temperature."""
        controller = FanController(dry_run=True)
        zones = controller._parse_step_zones("55:60,35:0,65:100,45:30")
        expected = [(35.0, 0.0), (45.0, 30.0), (55.0, 60.0), (65.0, 100.0)]
        self.assertEqual(zones, expected)

    def test_parse_step_zones_invalid_fallback(self):
        """Test that invalid zone config falls back to defaults."""
        controller = FanController(dry_run=True)
        zones = controller._parse_step_zones("invalid:data:here")
        # Should fallback to default zones
        self.assertEqual(len(zones), 4)
        self.assertTrue(all(isinstance(z, tuple) and len(z) == 2 for z in zones))

    def test_parse_step_zones_with_spaces(self):
        """Test parsing zones with extra whitespace."""
        controller = FanController(dry_run=True)
        zones = controller._parse_step_zones(" 35 : 0 , 45 : 30 , 55 : 60 ")
        expected = [(35.0, 0.0), (45.0, 30.0), (55.0, 60.0)]
        self.assertEqual(zones, expected)


class TestStepCurveCalculation(unittest.TestCase):
    """Tests for step curve duty calculation with hysteresis."""

    def setUp(self):
        """Set up controller with step curve for testing."""
        # Create a temporary config file with step curve
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_config.conf"
        self.config_file.write_text(
            """
MODE=auto
TEMP_LOW=30
TEMP_HIGH=70
FAN_SPEED_LOW=0
FAN_SPEED_HIGH=100
FAN_CURVE=step
STEP_ZONES=35:0,45:30,55:60,65:100
STEP_HYSTERESIS=2
"""
        )

        self.controller = FanController(dry_run=True, config_path=str(self.config_file))
        self.controller.start()

    def test_temp_below_first_zone(self):
        """Test temperature below first zone threshold."""
        duty = self.controller._calculate_step_duty(30.0)
        self.assertEqual(duty, 0.0)

    def test_temp_at_zone_boundary(self):
        """Test temperature exactly at zone boundary."""
        duty = self.controller._calculate_step_duty(45.0)
        self.assertEqual(duty, 30.0)

    def test_temp_between_zones(self):
        """Test temperature between zone boundaries."""
        duty = self.controller._calculate_step_duty(50.0)
        self.assertEqual(duty, 30.0)  # Should stay in 45-55 zone

    def test_temp_in_highest_zone(self):
        """Test temperature in highest zone."""
        duty = self.controller._calculate_step_duty(70.0)
        self.assertEqual(duty, 100.0)

    def test_hysteresis_rising_temperature(self):
        """Test hysteresis when temperature is rising."""
        # Start below first threshold
        self.controller.current_step_index = 0
        duty1 = self.controller._calculate_step_duty(34.0)
        self.assertEqual(duty1, 0.0)

        # Cross first threshold - should move to next zone
        duty2 = self.controller._calculate_step_duty(45.0)
        self.assertEqual(duty2, 30.0)
        self.assertEqual(self.controller.current_step_index, 1)

    def test_hysteresis_falling_temperature(self):
        """Test hysteresis when temperature is falling."""
        # Start in higher zone
        self.controller.current_step_index = 2  # 55:60 zone
        duty1 = self.controller._calculate_step_duty(56.0)
        self.assertEqual(duty1, 60.0)

        # Drop just below threshold (within hysteresis) - should stay
        duty2 = self.controller._calculate_step_duty(54.0)
        self.assertEqual(duty2, 60.0)
        self.assertEqual(self.controller.current_step_index, 2)

        # Drop below threshold minus hysteresis - should move down
        duty3 = self.controller._calculate_step_duty(52.0)
        self.assertEqual(duty3, 30.0)
        self.assertEqual(self.controller.current_step_index, 1)

    def test_hysteresis_prevents_oscillation(self):
        """Test that hysteresis prevents rapid zone switching."""
        # Start just below a zone boundary
        self.controller.current_step_index = 1  # 45:30 zone
        duty1 = self.controller._calculate_step_duty(54.5)
        self.assertEqual(duty1, 30.0)
        self.assertEqual(self.controller.current_step_index, 1)

        # Cross boundary - move to next zone
        duty2 = self.controller._calculate_step_duty(55.0)
        self.assertEqual(duty2, 60.0)
        self.assertEqual(self.controller.current_step_index, 2)

        # Drop slightly (within hysteresis) - should NOT move back
        duty3 = self.controller._calculate_step_duty(54.5)
        self.assertEqual(duty3, 60.0)
        self.assertEqual(self.controller.current_step_index, 2)


class TestConfigLoading(unittest.TestCase):
    """Tests for loading fan curve configuration from file."""

    def test_load_config_exponential(self):
        """Test loading exponential curve configuration."""
        temp_dir = tempfile.mkdtemp()
        config_file = Path(temp_dir) / "test_config.conf"
        config_file.write_text(
            """
MODE=auto
FAN_CURVE=exponential
"""
        )

        config = load_config(str(config_file))
        self.assertEqual(config["fan_curve"], "exponential")

    def test_load_config_linear(self):
        """Test loading linear curve configuration."""
        temp_dir = tempfile.mkdtemp()
        config_file = Path(temp_dir) / "test_config.conf"
        config_file.write_text(
            """
MODE=auto
FAN_CURVE=linear
"""
        )

        config = load_config(str(config_file))
        self.assertEqual(config["fan_curve"], "linear")

    def test_load_config_step_with_zones(self):
        """Test loading step curve with zone configuration."""
        temp_dir = tempfile.mkdtemp()
        config_file = Path(temp_dir) / "test_config.conf"
        config_file.write_text(
            """
MODE=auto
FAN_CURVE=step
STEP_ZONES=40:10,50:40,60:80
STEP_HYSTERESIS=3
"""
        )

        config = load_config(str(config_file))
        self.assertEqual(config["fan_curve"], "step")
        self.assertEqual(config["step_zones"], "40:10,50:40,60:80")
        self.assertEqual(config["step_hysteresis"], 3.0)

    def test_load_config_defaults(self):
        """Test that missing config uses exponential default."""
        temp_dir = tempfile.mkdtemp()
        config_file = Path(temp_dir) / "test_config.conf"
        config_file.write_text("MODE=auto\n")

        config = load_config(str(config_file))
        self.assertEqual(config["fan_curve"], "exponential")  # Default


class TestFanCurveIntegration(unittest.TestCase):
    """Integration tests for fan curves with FanController."""

    def test_controller_uses_exponential_curve(self):
        """Test that controller properly uses exponential curve from config."""
        temp_dir = tempfile.mkdtemp()
        config_file = Path(temp_dir) / "test_config.conf"
        config_file.write_text(
            """
MODE=auto
TEMP_LOW=30
TEMP_HIGH=70
FAN_SPEED_LOW=0
FAN_SPEED_HIGH=100
FAN_CURVE=exponential
"""
        )

        controller = FanController(dry_run=True, config_path=str(config_file))
        self.assertEqual(controller.fan_curve, "exponential")
        self.assertEqual(controller.min_temp, 30.0)
        self.assertEqual(controller.max_temp, 70.0)

    def test_controller_uses_linear_curve(self):
        """Test that controller properly uses linear curve from config."""
        temp_dir = tempfile.mkdtemp()
        config_file = Path(temp_dir) / "test_config.conf"
        config_file.write_text(
            """
MODE=auto
FAN_CURVE=linear
"""
        )

        controller = FanController(dry_run=True, config_path=str(config_file))
        self.assertEqual(controller.fan_curve, "linear")

    def test_controller_uses_step_curve(self):
        """Test that controller properly uses step curve from config."""
        temp_dir = tempfile.mkdtemp()
        config_file = Path(temp_dir) / "test_config.conf"
        config_file.write_text(
            """
MODE=auto
FAN_CURVE=step
STEP_ZONES=35:0,45:30,55:60,65:100
STEP_HYSTERESIS=2
"""
        )

        controller = FanController(dry_run=True, config_path=str(config_file))
        self.assertEqual(controller.fan_curve, "step")
        self.assertEqual(len(controller.step_zones), 4)
        self.assertEqual(controller.step_hysteresis, 2.0)

    def test_manual_mode_ignores_curve(self):
        """Test that manual mode doesn't use fan curve configuration."""
        temp_dir = tempfile.mkdtemp()
        config_file = Path(temp_dir) / "test_config.conf"
        config_file.write_text(
            """
MODE=manual
MANUAL_SPEED=75
FAN_CURVE=exponential
"""
        )

        controller = FanController(dry_run=True, config_path=str(config_file))
        self.assertEqual(controller.mode, "manual")
        self.assertEqual(controller.manual_speed, 75.0)
        # fan_curve should still be initialized but not used
        self.assertEqual(controller.fan_curve, "linear")  # Default for manual mode


if __name__ == "__main__":
    unittest.main()
