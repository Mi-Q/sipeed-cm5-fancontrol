import unittest
from fan_control import temp_to_duty


class TestMapping(unittest.TestCase):
    def test_below_min(self):
        self.assertEqual(temp_to_duty(30.0, min_temp=45.0, max_temp=60.0, min_duty=25.0), 25.0)

    def test_at_min(self):
        self.assertEqual(temp_to_duty(45.0, min_temp=45.0, max_temp=60.0, min_duty=25.0), 25.0)

    def test_at_max(self):
        self.assertEqual(temp_to_duty(60.0, min_temp=45.0, max_temp=60.0, min_duty=25.0), 100.0)

    def test_above_max(self):
        self.assertEqual(temp_to_duty(70.0, min_temp=45.0, max_temp=60.0, min_duty=25.0), 100.0)

    def test_mid(self):
        # 52.5C is halfway between 45 and 60, so duty should be halfway between 25 and 100 --> 62.5
        d = temp_to_duty(52.5, min_temp=45.0, max_temp=60.0, min_duty=25.0)
        self.assertAlmostEqual(d, 62.5, places=3)


if __name__ == '__main__':
    unittest.main()
