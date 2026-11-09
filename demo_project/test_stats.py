import unittest
from stats import mean, median


class StatsTests(unittest.TestCase):
    def test_mean(self):
        self.assertEqual(mean([2, 4, 6]), 4)

    def test_mean_empty(self):
        with self.assertRaises(ValueError):
            mean([])

    def test_median_even(self):
        self.assertEqual(median([4, 1, 2, 3]), 2.5)

    def test_median_odd(self):
        self.assertEqual(median([8, 1, 3]), 3)

    def test_median_empty(self):
        with self.assertRaises(ValueError):
            median([])


if __name__ == "__main__":
    unittest.main()

