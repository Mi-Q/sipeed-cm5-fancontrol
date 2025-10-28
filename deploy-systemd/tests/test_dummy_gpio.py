"""Tests for Dummy GPIO and PWM implementations."""

import unittest

from fan_control import DummyGPIO, DummyPWM


class TestDummyPWM(unittest.TestCase):
    """Tests for DummyPWM class."""

    def test_initialization(self):
        """Test DummyPWM initialization."""
        pwm = DummyPWM(pin=13, freq=50)
        self.assertEqual(pwm.pin, 13)
        self.assertEqual(pwm.freq, 50)
        self.assertIsNone(pwm._duty)

    def test_start(self):
        """Test PWM start method."""
        pwm = DummyPWM(pin=13, freq=50)
        pwm.start(25.0)
        self.assertEqual(pwm._duty, 25.0)

    def test_change_duty_cycle(self):
        """Test change_duty_cycle method."""
        pwm = DummyPWM(pin=13, freq=50)
        pwm.start(25.0)
        pwm.change_duty_cycle(50.0)
        self.assertEqual(pwm._duty, 50.0)

    def test_change_duty_cycle_alias(self):
        """Test ChangeDutyCycle alias for RPi.GPIO compatibility."""
        pwm = DummyPWM(pin=13, freq=50)
        pwm.start(25.0)
        # Should work with capital letters (RPi.GPIO style)
        pwm.ChangeDutyCycle(75.0)
        self.assertEqual(pwm._duty, 75.0)

    def test_stop(self):
        """Test PWM stop method."""
        pwm = DummyPWM(pin=13, freq=50)
        pwm.start(50.0)
        # stop() should not raise an exception
        pwm.stop()

    def test_multiple_duty_changes(self):
        """Test multiple duty cycle changes."""
        pwm = DummyPWM(pin=13, freq=50)
        pwm.start(25.0)
        self.assertEqual(pwm._duty, 25.0)

        pwm.change_duty_cycle(50.0)
        self.assertEqual(pwm._duty, 50.0)

        pwm.change_duty_cycle(75.0)
        self.assertEqual(pwm._duty, 75.0)

        pwm.change_duty_cycle(100.0)
        self.assertEqual(pwm._duty, 100.0)


class TestDummyGPIO(unittest.TestCase):
    """Tests for DummyGPIO class."""

    def test_constants(self):
        """Test GPIO constants are defined."""
        self.assertEqual(DummyGPIO.BCM, "BCM")
        self.assertEqual(DummyGPIO.OUT, "OUT")

    def test_setmode(self):
        """Test setmode method."""
        gpio = DummyGPIO()
        # Should not raise an exception
        gpio.setmode(DummyGPIO.BCM)

    def test_setup(self):
        """Test setup method."""
        gpio = DummyGPIO()
        # Should not raise an exception
        gpio.setup(13, DummyGPIO.OUT)

    def test_pwm_creation(self):
        """Test PWM object creation."""
        gpio = DummyGPIO()
        pwm = gpio.PWM(13, 50)
        self.assertIsInstance(pwm, DummyPWM)
        self.assertEqual(pwm.pin, 13)
        self.assertEqual(pwm.freq, 50)

    def test_cleanup(self):
        """Test cleanup method."""
        gpio = DummyGPIO()
        # Should not raise an exception
        gpio.cleanup()

    def test_full_gpio_workflow(self):
        """Test complete GPIO setup and usage workflow."""
        gpio = DummyGPIO()

        # Setup GPIO
        gpio.setmode(DummyGPIO.BCM)
        gpio.setup(13, DummyGPIO.OUT)

        # Create and use PWM
        pwm = gpio.PWM(13, 50)
        pwm.start(25.0)
        pwm.change_duty_cycle(50.0)
        pwm.stop()

        # Cleanup
        gpio.cleanup()


class TestDummyGPIOIntegration(unittest.TestCase):
    """Integration tests for DummyGPIO and DummyPWM."""

    def test_multiple_pwm_instances(self):
        """Test creating multiple PWM instances."""
        gpio = DummyGPIO()
        gpio.setmode(DummyGPIO.BCM)

        pwm1 = gpio.PWM(13, 50)
        pwm2 = gpio.PWM(18, 100)

        self.assertEqual(pwm1.pin, 13)
        self.assertEqual(pwm1.freq, 50)
        self.assertEqual(pwm2.pin, 18)
        self.assertEqual(pwm2.freq, 100)

        pwm1.start(25.0)
        pwm2.start(50.0)

        self.assertEqual(pwm1._duty, 25.0)
        self.assertEqual(pwm2._duty, 50.0)

    def test_pwm_independent_operation(self):
        """Test that PWM instances operate independently."""
        gpio = DummyGPIO()

        pwm1 = gpio.PWM(13, 50)
        pwm2 = gpio.PWM(18, 50)

        pwm1.start(30.0)
        pwm2.start(60.0)

        pwm1.change_duty_cycle(40.0)

        # PWM1 should change, PWM2 should remain the same
        self.assertEqual(pwm1._duty, 40.0)
        self.assertEqual(pwm2._duty, 60.0)


if __name__ == "__main__":
    unittest.main()
