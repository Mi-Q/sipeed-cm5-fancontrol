"""Integration tests for end-to-end workflows."""

import unittest
from unittest.mock import patch

from fan_control import FanController, parse_args


class TestParseArgs(unittest.TestCase):
    """Tests for argument parsing."""

    def test_default_args(self):
        """Test default argument values."""
        with patch("sys.argv", ["fan_control.py"]):
            args = parse_args()
            self.assertEqual(args.pin, 13)
            self.assertEqual(args.freq, 1000)
            self.assertEqual(args.poll, 5)
            self.assertEqual(args.min_duty, 30.0)
            self.assertEqual(args.min_temp, 45.0)
            self.assertEqual(args.max_temp, 65.0)  # Updated default
            self.assertFalse(args.dry_run)
            self.assertIsNone(args.simulate_temp)
            self.assertEqual(args.peers, "")
            self.assertEqual(args.remote_method, "ssh")

    def test_dry_run_flag(self):
        """Test --dry-run flag."""
        with patch("sys.argv", ["fan_control.py", "--dry-run"]):
            args = parse_args()
            self.assertTrue(args.dry_run)

    def test_simulate_temp(self):
        """Test --simulate-temp argument."""
        with patch("sys.argv", ["fan_control.py", "--simulate-temp", "55.5"]):
            args = parse_args()
            self.assertEqual(args.simulate_temp, 55.5)

    def test_custom_pin(self):
        """Test custom pin number."""
        with patch("sys.argv", ["fan_control.py", "--pin", "18"]):
            args = parse_args()
            self.assertEqual(args.pin, 18)

    def test_custom_temperatures(self):
        """Test custom temperature thresholds."""
        with patch(
            "sys.argv",
            [
                "fan_control.py",
                "--min-temp",
                "40.0",
                "--max-temp",
                "65.0",
                "--min-duty",
                "20.0",
            ],
        ):
            args = parse_args()
            self.assertEqual(args.min_temp, 40.0)
            self.assertEqual(args.max_temp, 65.0)
            self.assertEqual(args.min_duty, 20.0)

    def test_peers(self):
        """Test peers configuration."""
        with patch("sys.argv", ["fan_control.py", "--peers", "host1,host2,user@host3"]):
            args = parse_args()
            self.assertEqual(args.peers, "host1,host2,user@host3")

    def test_remote_method(self):
        """Test --remote-method flag."""
        with patch("sys.argv", ["fan_control.py", "--remote-method", "http"]):
            args = parse_args()
            self.assertEqual(args.remote_method, "http")


class TestFanControllerIntegration(unittest.TestCase):
    """Integration tests for FanController workflows."""

    @patch("fan_control.read_cpu_temp")
    @patch("fan_control.time.sleep")
    def test_dry_run_workflow(self, mock_sleep, mock_read_temp):
        """Test complete dry-run workflow."""
        mock_read_temp.return_value = 50.0
        mock_sleep.side_effect = [None, KeyboardInterrupt]

        controller = FanController(
            pin=13,
            freq=50,
            poll=5,
            min_duty=25.0,
            min_temp=45.0,
            max_temp=60.0,
            dry_run=True,
        )

        # Start and run once
        controller.start()
        result = controller.run_once()
        self.assertIsNotNone(result)

    def test_simulated_temp_workflow(self):
        """Test workflow with simulated temperature."""
        controller = FanController(
            pin=13,
            freq=50,
            poll=5,
            dry_run=True,
            simulate_temp=55.0,
        )

        controller.start()
        result = controller.run_once()
        self.assertIsNotNone(result)
        self.assertEqual(result["per_host"]["local"], 55.0)

    @patch("fan_control.read_cpu_temp")
    def test_temperature_threshold_behavior(self, mock_read_temp):
        """Test duty cycle behavior at different temperatures."""
        controller = FanController(
            pin=13,
            freq=1000,
            poll=5,
            min_duty=30.0,
            min_temp=45.0,
            max_temp=60.0,
            dry_run=True,
        )
        controller.start()

        # Test below minimum
        mock_read_temp.return_value = 40.0
        result = controller.run_once()
        self.assertIsNotNone(result)
        self.assertEqual(result["duty"], 30.0)

        # Test above maximum
        mock_read_temp.return_value = 70.0
        result = controller.run_once()
        self.assertIsNotNone(result)
        self.assertEqual(result["duty"], 100.0)

    def test_controller_cleanup_workflow(self):
        """Test cleanup is called properly."""
        controller = FanController(
            pin=13,
            freq=50,
            poll=5,
            dry_run=True,
        )
        controller.start()

        # Trigger cleanup
        controller.stop()
        self.assertFalse(controller._running)

    @patch("fan_control.read_cpu_temp")
    def test_none_temperature_handling(self, mock_read_temp):
        """Test handling when temperature reading returns None."""
        mock_read_temp.return_value = None

        controller = FanController(
            pin=13,
            freq=50,
            poll=5,
            dry_run=True,
        )
        controller.start()

        result = controller.run_once()
        # Should return None when read fails
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
