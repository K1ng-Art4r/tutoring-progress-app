import unittest

from app.exam_config import EGE_BASE_CONFIG, grade_for_score
from app.progress_forecast import (
    calculate_ege_base_model_score,
    smooth_ege_base_score,
    update_ege_base_mastery,
)


class EgeBaseConfigTests(unittest.TestCase):
    def test_competency_weights_equal_max_primary_score(self):
        self.assertEqual(
            sum(item.weight for item in EGE_BASE_CONFIG.competencies),
            EGE_BASE_CONFIG.max_primary_score,
        )

    def test_grade_boundaries_use_continuous_score(self):
        cases = {
            0: 2,
            6.9: 2,
            7: 3,
            11.9: 3,
            12: 4,
            16.9: 4,
            17: 5,
            21: 5,
        }
        for score, expected_grade in cases.items():
            with self.subTest(score=score):
                self.assertEqual(grade_for_score(EGE_BASE_CONFIG, score), expected_grade)

    def test_model_score_is_weighted_and_clamped(self):
        competencies = [
            {"weight": 1, "level": 0.9},
            {"weight": 2, "level": 0.8},
            {"weight": 3, "level": 0.6},
            {"weight": 2, "level": 0.4},
        ]
        self.assertAlmostEqual(calculate_ege_base_model_score(competencies), 5.1)
        self.assertEqual(
            calculate_ege_base_model_score([{"weight": 30, "level": 1.0}]),
            21.0,
        )

    def test_smoothing_respects_event_delta_limit(self):
        self.assertAlmostEqual(smooth_ege_base_score(10, 20, "homework"), 10.3)
        self.assertAlmostEqual(smooth_ege_base_score(10, 20, "lesson"), 10.6)
        self.assertAlmostEqual(smooth_ege_base_score(10, 20, "mini_diagnostic"), 11.0)
        self.assertAlmostEqual(smooth_ege_base_score(10, 20, "checkpoint"), 11.5)
        self.assertAlmostEqual(smooth_ege_base_score(10, 20, "full_mock"), 13.0)

    def test_mastery_uses_event_learning_rate(self):
        self.assertAlmostEqual(update_ege_base_mastery(0.5, 1.0, "homework"), 0.56)
        self.assertAlmostEqual(update_ege_base_mastery(0.5, 1.0, "lesson"), 0.60)
        self.assertAlmostEqual(update_ege_base_mastery(0.5, 1.0, "mini_diagnostic"), 0.675)
        self.assertAlmostEqual(update_ege_base_mastery(0.5, 1.0, "checkpoint"), 0.75)
        self.assertAlmostEqual(update_ege_base_mastery(0.5, 1.0, "full_mock"), 0.825)


if __name__ == "__main__":
    unittest.main()
