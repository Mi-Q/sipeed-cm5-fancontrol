"""Tests for FanController class."""

import signal
import sys
import unittest
from unittest.mock import MagicMock, patch

from fan_control import FanController, import_gpio


class TestImportGPIO(unittest.TestCase):
    """Tests for import_gpio function."""

    def test_dry_run_returns_dummy(self):
        """Test that dry-run mode returns DummyGPIO."""
        gpio_module = import_gpio(dry_run=True)
        self.assertEqual(gpio_module.__class__.__name__, "DummyGPIO")

    def test_rpi_gpio_not_available_fallback(self):
        """Test fallback to DummyGPIO when RPi.GPIO import fails."""
        # Block the RPi.GPIO import
        with patch.dict(sys.modules, {"RPi": None, "RPi.GPIO": None}):
            with patch("fan_control.logger") as mock_logger:
                gpio_module = import_gpio(dry_run=False)
                # Should return DummyGPIO instance
                self.assertEqual(gpio_module.__class__.__name__, "DummyGPIO")
                # Should log warning
                mock_logger.warning.assert_called_once()
                self.assertIn("RPi.GPIO not available", mock_logger.warning.call_args[0][0])

    def test_rpi_gpio_available_success(self):
        """Test successful import of real RPi.GPIO module."""
        # Create a mock RPi module with GPIO submodule
        mock_rpi = MagicMock()
        mock_gpio = MagicMock()
        mock_gpio.__name__ = "RPi.GPIO"
        mock_rpi.GPIO = mock_gpio

        # Mock the import to succeed
        with patch.dict(sys.modules, {"RPi": mock_rpi, "RPi.GPIO": mock_gpio}):
            gpio_module = import_gpio(dry_run=False)
            # Should return the actual GPIO module (not DummyGPIO)
            # Check it's not DummyGPIO by verifying it's not an instance
            self.assertNotEqual(gpio_module.__class__.__name__, "DummyGPIO")


class TestFanController(unittest.TestCase):
    """Tests for FanController class."""

    def test_initialization(self):
        """Test FanController initialization."""
        controller = FanController(
            pin=13,
            freq=25000,
            poll=5,
            min_duty=30.0,
            min_temp=45.0,
            max_temp=60.0,
            dry_run=True,
            simulate_temp=None,
        )
        self.assertEqual(controller.pin, 13)
        self.assertEqual(controller.freq, 25000)
        self.assertEqual(controller.poll, 5)
        self.assertEqual(controller.min_duty, 30.0)
        self.assertEqual(controller.min_temp, 45.0)
        self.assertEqual(controller.max_temp, 60.0)
        self.assertIsNotNone(controller.pwm)
        self.assertIsNotNone(controller.GPIO)

    def test_update_duty_cycle_below_min(self):
        """Test that minimum duty cycle is enforced."""
        controller = FanController(
            pin=13,
            freq=50,
            poll=5,
            min_duty=25.0,
            min_temp=45.0,
            max_temp=60.0,
            dry_run=True,
        )
        controller.start()
        # Duty cycle should never go below min_duty
        self.assertGreaterEqual(controller.last_duty, 25.0)

    def test_stop_and_cleanup(self):
        """Test stop method."""
        controller = FanController(
            pin=13,
            freq=50,
            poll=5,
            dry_run=True,
        )
        controller.start()
        self.assertTrue(controller._running)
        controller.stop()
        self.assertFalse(controller._running)

    @patch("fan_control.read_cpu_temp")
    def test_run_once_success(self, mock_read_temp):
        """Test successful run_once execution."""
        mock_read_temp.return_value = 50.0
        controller = FanController(
            pin=13,
            freq=50,
            poll=5,
            dry_run=True,
        )
        controller.start()
        result = controller.run_once()
        self.assertIsNotNone(result)
        self.assertIn("local", result["per_host"])
        self.assertEqual(result["per_host"]["local"], 50.0)
        self.assertIn("aggregated_temp", result)
        self.assertIn("duty", result)

    @patch("fan_control.read_cpu_temp")
    def test_run_once_failure(self, mock_read_temp):
        """Test run_once when temperature reading fails."""
        mock_read_temp.return_value = None
        controller = FanController(
            pin=13,
            freq=50,
            poll=5,
            dry_run=True,
        )
        controller.start()
        result = controller.run_once()
        self.assertIsNone(result)

    def test_stop_with_attribute_errors(self):
        """Test stop method handles AttributeErrors gracefully."""
        controller = FanController(
            pin=13,
            freq=50,
            poll=5,
            dry_run=True,
        )
        controller.start()

        # Mock pwm.stop() to raise AttributeError
        controller.pwm.stop = MagicMock(side_effect=AttributeError("stop not found"))
        # Mock GPIO.cleanup() to raise AttributeError
        controller.GPIO.cleanup = MagicMock(side_effect=AttributeError("cleanup not found"))

        # Should not raise exception
        controller.stop()
        self.assertFalse(controller._running)

    @patch("fan_control.read_cpu_temp")
    def test_change_duty_cycle_attribute_error(self, mock_read_temp):
        """Test that AttributeError in ChangeDutyCycle is handled gracefully."""
        mock_read_temp.return_value = 55.0
        controller = FanController(
            pin=13,
            freq=50,
            poll=5,
            dry_run=True,
        )
        controller.start()

        # Mock ChangeDutyCycle to raise AttributeError
        controller.pwm.ChangeDutyCycle = MagicMock(side_effect=AttributeError("Method not found"))

        with patch("fan_control.logger") as mock_logger:
            result = controller.run_once()
            # Should still return result
            self.assertIsNotNone(result)
            # Should log warning
            mock_logger.warning.assert_called()
            self.assertIn("Failed to set duty cycle", mock_logger.warning.call_args[0][0])

    @patch("fan_control.read_cpu_temp")
    def test_all_temps_fail(self, mock_read_temp):
        """Test error logging when local temperature read fails."""
        mock_read_temp.return_value = None
        controller = FanController(
            pin=13,
            freq=50,
            poll=5,
            dry_run=True,
        )
        controller.start()

        with patch("fan_control.logger") as mock_logger:
            result = controller.run_once()
            self.assertIsNone(result)
            # Should log error about failed local temp reading
            mock_logger.error.assert_called()
            self.assertIn("Failed to read local", mock_logger.error.call_args[0][0])

    @patch("fan_control.signal.signal")
    @patch("fan_control.time.sleep")
    @patch("fan_control.read_cpu_temp")
    def test_signal_handlers_registered(self, mock_read_temp, mock_sleep, mock_signal):
        """Test that SIGTERM and SIGINT handlers are registered in run_loop."""
        mock_read_temp.return_value = 50.0
        # Make sleep raise exception to exit loop after signal handlers registered
        mock_sleep.side_effect = KeyboardInterrupt()

        controller = FanController(
            pin=13,
            freq=50,
            poll=5,
            dry_run=True,
        )

        try:
            controller.run_loop()
        except KeyboardInterrupt:
            # Expected interruption to stop the run loop
            pass

        # Verify signal handlers were registered
        self.assertEqual(mock_signal.call_count, 2)
        # Get the signal types that were registered
        registered_signals = [call[0][0] for call in mock_signal.call_args_list]
        self.assertIn(signal.SIGTERM, registered_signals)
        self.assertIn(signal.SIGINT, registered_signals)

    @patch("fan_control.read_cpu_temp")
    def test_run_loop_handles_os_error(self, mock_read_temp):
        """Test that run_loop handles OSError gracefully."""
        # First call succeeds, second raises OSError, third succeeds
        mock_read_temp.side_effect = [
            50.0,
            OSError("I/O error"),
            51.0,
            KeyboardInterrupt(),
        ]

        controller = FanController(
            pin=13,
            freq=50,
            poll=0.01,  # Very short poll to speed up test
            dry_run=True,
        )

        with patch("fan_control.logger") as mock_logger:
            with patch("fan_control.time.sleep"):
                try:
                    controller.run_loop()
                except KeyboardInterrupt:
                    # Expected interruption to stop the run loop
                    pass

                # Should log exception
                mock_logger.exception.assert_called()
                self.assertIn("Error in run loop", mock_logger.exception.call_args[0][0])

    def test_gpio_setup_attribute_errors(self):
        """Test that GPIO setup handles AttributeError gracefully."""
        # Create a mock GPIO module that raises AttributeError on setmode and setup
        mock_gpio = MagicMock()
        mock_gpio.BCM = 11
        mock_gpio.OUT = 0
        mock_gpio.setmode.side_effect = AttributeError("setmode not found")
        mock_gpio.setup.side_effect = AttributeError("setup not found")
        mock_gpio.PWM.side_effect = AttributeError("PWM not found")

        # Patch import_gpio to return our mock GPIO
        with patch("fan_control.import_gpio", return_value=mock_gpio):
            controller = FanController(
                pin=13,
                freq=50,
                poll=5,
                dry_run=False,
            )
            # Should have fallen back to DummyPWM
            self.assertEqual(controller.pwm.__class__.__name__, "DummyPWM")

    @patch("fan_control.read_cpu_temp")
    @patch("fan_control.read_remote_temp_http")
    def test_all_peers_fail_no_valid_temps(self, mock_http, mock_local):
        """Test error when local succeeds but all peers fail leaving only one valid temp."""
        # This tests a different path where we have peers configured
        mock_local.return_value = 50.0
        mock_http.return_value = None  # All peers fail

        controller = FanController(pin=13, freq=50, poll=5, dry_run=True)
        controller.peers = ["http://peer1:2505/temp", "http://peer2:2505/temp"]
        controller.remote_method = "http"
        controller.start()

        result = controller.run_once()
        # Should still work with just local temp
        self.assertIsNotNone(result)
        self.assertEqual(result["per_host"]["local"], 50.0)
        self.assertIsNone(result["per_host"]["http://peer1:2505/temp"])

    @patch("fan_control.signal.signal")
    @patch("fan_control.time.sleep")
    @patch("fan_control.read_cpu_temp")
    @patch("fan_control.sys.exit")
    def test_signal_handler_execution(self, mock_exit, mock_read_temp, mock_sleep, mock_signal):
        """Test that signal handler actually calls stop() and sys.exit()."""
        mock_read_temp.return_value = 50.0

        # Capture the signal handler function
        signal_handlers = {}

        def capture_handler(sig, handler):
            signal_handlers[sig] = handler

        mock_signal.side_effect = capture_handler

        # Make sleep raise exception after handlers are set
        mock_sleep.side_effect = KeyboardInterrupt()

        controller = FanController(pin=13, freq=50, poll=5, dry_run=True)

        try:
            controller.run_loop()
        except KeyboardInterrupt:
            # Expected interruption to stop the run loop
            pass

        # Get the SIGTERM handler
        sigterm_handler = signal_handlers.get(signal.SIGTERM)
        self.assertIsNotNone(sigterm_handler)

        # Call the handler
        with patch("fan_control.logger") as mock_logger:
            sigterm_handler(signal.SIGTERM, None)

            # Verify it logged the signal message
            # Look through all info calls to find the one about receiving signal
            info_calls = [str(call) for call in mock_logger.info.call_args_list]
            signal_logged = any("Received signal" in str(call) for call in info_calls)
            self.assertTrue(signal_logged, "Should log message about receiving signal")

            # Verify stop was called (controller should no longer be running)
            self.assertFalse(controller._running)

            # Verify sys.exit was called
            mock_exit.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()
