import unittest

from app.exam_config import EGE_PROFILE_CONFIG, ege_profile_test_score
from app.progress_forecast import calculate_ege_profile_primary_score


class EgeProfileConfigTests(unittest.TestCase):
    def test_competency_weights_equal_32(self):
        self.assertEqual(sum(item.weight for item in EGE_PROFILE_CONFIG.competencies), 32)
        self.assertEqual(EGE_PROFILE_CONFIG.max_primary_score, 32)
        self.assertEqual(EGE_PROFILE_CONFIG.max_test_score, 100)
        self.assertEqual(EGE_PROFILE_CONFIG.exam_year, 2026)

    def test_primary_to_test_boundaries(self):
        self.assertEqual(ege_profile_test_score(0), 0)
        self.assertEqual(ege_profile_test_score(5), 27)
        self.assertEqual(ege_profile_test_score(16), 78)
        self.assertEqual(ege_profile_test_score(17), 80)
        self.assertEqual(ege_profile_test_score(32), 100)

    def test_primary_to_test_uses_linear_interpolation(self):
        self.assertEqual(ege_profile_test_score(16.5), 79)
        self.assertAlmostEqual(ege_profile_test_score(5.5), 30.5)

    def test_profile_model_score_is_weighted_and_clamped(self):
        rows = [{"weight": item.weight, "level": 0.5} for item in EGE_PROFILE_CONFIG.competencies]
        self.assertEqual(calculate_ege_profile_primary_score(rows), 16.0)
        self.assertEqual(calculate_ege_profile_primary_score([{"weight": 50, "level": 1}]), 32.0)


if __name__ == "__main__":
    unittest.main()
