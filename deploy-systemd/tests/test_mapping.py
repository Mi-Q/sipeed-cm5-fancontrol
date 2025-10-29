import unittest

from fan_control import temp_to_duty


class TestMapping(unittest.TestCase):
    """Test linear fan curve mapping (original behavior)."""

    def test_below_min(self):
        self.assertEqual(
            temp_to_duty(30.0, min_temp=45.0, max_temp=60.0, min_duty=25.0), 25.0
        )

    def test_at_min(self):
        self.assertEqual(
            temp_to_duty(45.0, min_temp=45.0, max_temp=60.0, min_duty=25.0), 25.0
        )

    def test_at_max(self):
        self.assertEqual(
            temp_to_duty(60.0, min_temp=45.0, max_temp=60.0, min_duty=25.0), 100.0
        )

    def test_above_max(self):
        self.assertEqual(
            temp_to_duty(70.0, min_temp=45.0, max_temp=60.0, min_duty=25.0), 100.0
        )

    def test_mid(self):
        # 52.5C is halfway between 45 and 60, so duty should be halfway between 25 and 100 --> 62.5
        d = temp_to_duty(52.5, min_temp=45.0, max_temp=60.0, min_duty=25.0)
        self.assertAlmostEqual(d, 62.5, places=3)


class TestExponentialCurve(unittest.TestCase):
    """Test exponential (quadratic) fan curve mapping."""

    def test_below_min(self):
        # Below min temp should return min_duty regardless of curve type
        self.assertEqual(
            temp_to_duty(
                30.0,
                min_temp=45.0,
                max_temp=60.0,
                min_duty=25.0,
                curve_type="exponential",
            ),
            25.0,
        )

    def test_at_min(self):
        self.assertEqual(
            temp_to_duty(
                45.0,
                min_temp=45.0,
                max_temp=60.0,
                min_duty=25.0,
                curve_type="exponential",
            ),
            25.0,
        )

    def test_at_max(self):
        self.assertEqual(
            temp_to_duty(
                60.0,
                min_temp=45.0,
                max_temp=60.0,
                min_duty=25.0,
                curve_type="exponential",
            ),
            100.0,
        )

    def test_above_max(self):
        self.assertEqual(
            temp_to_duty(
                70.0,
                min_temp=45.0,
                max_temp=60.0,
                min_duty=25.0,
                curve_type="exponential",
            ),
            100.0,
        )

    def test_mid_exponential_lower_than_linear(self):
        # At midpoint (52.5C), exponential should be lower than linear
        # Linear at midpoint: 62.5
        # Exponential: ratio=0.5, ratio^2=0.25, duty = 25 + 0.25*75 = 43.75
        d = temp_to_duty(
            52.5, min_temp=45.0, max_temp=60.0, min_duty=25.0, curve_type="exponential"
        )
        self.assertAlmostEqual(d, 43.75, places=3)

        # Verify it's lower than linear
        d_linear = temp_to_duty(
            52.5, min_temp=45.0, max_temp=60.0, min_duty=25.0, curve_type="linear"
        )
        self.assertLess(d, d_linear)

    def test_early_temp_stays_quiet(self):
        # At 35°C with range 30-70, exponential should be very low
        # ratio = (35-30)/(70-30) = 0.125
        # ratio^2 = 0.015625
        # duty = 0 + 0.015625*100 = 1.5625
        d = temp_to_duty(
            35.0, min_temp=30.0, max_temp=70.0, min_duty=0.0, curve_type="exponential"
        )
        self.assertAlmostEqual(d, 1.5625, places=3)
        self.assertLess(d, 5.0)  # Very quiet at low temps

    def test_high_temp_ramps_fast(self):
        # At 65°C with range 30-70, exponential should be high
        # ratio = (65-30)/(70-30) = 0.875
        # ratio^2 = 0.765625
        # duty = 0 + 0.765625*100 = 76.5625
        d = temp_to_duty(
            65.0, min_temp=30.0, max_temp=70.0, min_duty=0.0, curve_type="exponential"
        )
        self.assertAlmostEqual(d, 76.5625, places=3)


class TestCurveComparison(unittest.TestCase):
    """Test that exponential curve is quieter at low temps but adequate at high temps."""

    def test_exponential_quieter_at_low_moderate_temps(self):
        # Test at various temperatures below 60% of range
        for temp in [35, 40, 45, 50]:
            d_linear = temp_to_duty(
                temp, min_temp=30.0, max_temp=70.0, min_duty=0.0, curve_type="linear"
            )
            d_exponential = temp_to_duty(
                temp,
                min_temp=30.0,
                max_temp=70.0,
                min_duty=0.0,
                curve_type="exponential",
            )
            self.assertLess(
                d_exponential,
                d_linear,
                f"At {temp}°C, exponential ({d_exponential:.1f}%) should be quieter than linear ({d_linear:.1f}%)",
            )

    def test_endpoints_identical(self):
        # At min and max, both curves should give same result
        for temp in [30.0, 70.0]:
            d_linear = temp_to_duty(
                temp, min_temp=30.0, max_temp=70.0, min_duty=0.0, curve_type="linear"
            )
            d_exponential = temp_to_duty(
                temp,
                min_temp=30.0,
                max_temp=70.0,
                min_duty=0.0,
                curve_type="exponential",
            )
            self.assertEqual(
                d_linear,
                d_exponential,
                f"At {temp}°C, linear and exponential should match",
            )


if __name__ == "__main__":
    unittest.main()
