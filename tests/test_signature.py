import unittest

from aegis_reconnect import signature
from aegis_reconnect.signature import Evaluation, decide, dominant_colour, estimate_scale, find_bands, match_ratio, near


class SignatureTest(unittest.TestCase):
    def test_near_checks_every_channel(self):
        self.assertTrue(near((10, 10, 10), (15, 5, 12), 5))
        self.assertFalse(near((10, 10, 10), (10, 10, 30), 5))

    def test_match_ratio_counts_close_points(self):
        ref = [[0, 0, 0]] * 4
        cur = [(0, 0, 0), (1, 1, 1), (200, 0, 0), (0, 0, 0)]
        self.assertEqual(match_ratio(cur, ref, 5), 0.75)

    def test_mismatched_lengths_never_match(self):
        self.assertEqual(match_ratio([(0, 0, 0)], [[0, 0, 0]] * 2, 5), 0.0)

    def test_dominant_colour_is_the_face(self):
        samples = [[111, 111, 111]] * 8 + [[255, 255, 255]] * 2
        self.assertEqual(dominant_colour(samples), (111, 111, 111))

    def test_scale_estimates(self):
        self.assertEqual([estimate_scale(h) for h in (16, 18, 33, 36, 54, 72)], [1, 1, 2, 2, 3, 4])

    def test_sample_grid_grows_with_scale_not_in_count(self):
        self.assertEqual(len(signature.offsets_for(1)), len(signature.offsets_for(4)))
        self.assertEqual(signature.offsets_for(3)[1][0], 3 * signature.offsets_for(1)[1][0])

    def test_bands_bridge_small_gaps_and_drop_specks(self):
        face_rows = set(range(100, 118)) | set(range(120, 130)) | {200, 201} | set(range(300, 318))
        bands = find_bands(lambda y: y in face_rows, 0, 400, min_run=10, merge_gap=3)
        self.assertEqual(bands, [(100, 129), (300, 317)])

    def test_decide_needs_a_good_match(self):
        self.assertIsNone(decide(Evaluation([100], [0.85]), 0.9, 0.08))
        self.assertEqual(decide(Evaluation([100], [0.95]), 0.9, 0.08), (100, 0.95))

    def test_decide_refuses_lookalikes(self):
        self.assertIsNone(decide(Evaluation([100, 160], [0.95, 0.93]), 0.9, 0.08))

    def test_decide_picks_the_clear_winner_among_several(self):
        self.assertEqual(decide(Evaluation([100, 160, 220], [0.6, 0.97, 0.7]), 0.9, 0.08), (160, 0.97))

    def test_decide_with_nothing_found(self):
        self.assertIsNone(decide(Evaluation([], []), 0.9, 0.08))


if __name__ == "__main__":
    unittest.main()
