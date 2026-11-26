import unittest

from aegis_reconnect import signature, vision
from aegis_reconnect.config import Calibration

from .synthetic import Screen

CX = 500
Y0 = 400  # where the Reconnect button was when calibrating


def calibrate(scale):
    """Record Reconnect on a screen with two buttons, once hovered and once not, as `calibrate` does."""
    offsets = signature.offsets_for(scale)
    layout = [(Y0, "Reconnect"), (Y0 + 24 * scale, "Back to Server List")]
    hover = signature.sample(Screen(layout, scale, CX, hovered=0).pixel, CX, Y0, offsets)
    idle = signature.sample(Screen(layout, scale, CX).pixel, CX, Y0, offsets)
    return Calibration(0, 0, [list(p) for p in idle], [list(p) for p in hover], scale=scale)


def find(screen, cal, scale, y=Y0, **kw):
    args = dict(tolerance=40, face_tolerance=14, min_ratio=0.9, margin=0.08)
    args.update(kw)
    return vision.find_reconnect(screen.pixel, cal, scale, CX, y, 0, 1080, **args)


class VisionTest(unittest.TestCase):
    def check_scales(self, fn):
        for scale in (1, 2, 3, 4):
            with self.subTest(scale=scale):
                fn(scale, calibrate(scale))

    def test_finds_it_on_the_screen_it_was_calibrated_on(self):
        def run(scale, cal):
            screen = Screen([(Y0, "Reconnect"), (Y0 + 24 * scale, "Back to Server List")], scale, CX)
            found = find(screen, cal, scale)
            self.assertEqual(found.target[1], Y0)
            self.assertEqual(found.button_count, 2)
        self.check_scales(run)

    def test_finds_it_with_three_buttons_and_the_stack_recentred(self):
        def run(scale, cal):
            top = Y0 - 12 * scale  # a third button pushes the stack up by half a pitch
            labels = ["Reconnect", "Back to Server List", "Quit Game"]
            screen = Screen([(top + i * 24 * scale, t) for i, t in enumerate(labels)], scale, CX)
            found = find(screen, cal, scale)
            self.assertEqual(found.target[1], top)
            self.assertEqual(found.button_count, 3)
            self.assertEqual(found.rank_from_top, 1)
        self.check_scales(run)

    def test_finds_it_when_it_is_not_the_top_button(self):
        def run(scale, cal):
            top = Y0 - 24 * scale
            labels = ["Back to Server List", "Reconnect", "Quit Game"]
            screen = Screen([(top + i * 24 * scale, t) for i, t in enumerate(labels)], scale, CX)
            found = find(screen, cal, scale)
            self.assertEqual(found.target[1], top + 24 * scale)
            self.assertEqual(found.rank_from_top, 2)
        self.check_scales(run)

    def test_finds_it_while_another_button_is_hovered(self):
        def run(scale, cal):
            labels = ["Reconnect", "Back to Server List", "Quit Game"]
            screen = Screen([(Y0 + i * 24 * scale, t) for i, t in enumerate(labels)], scale, CX, hovered=2)
            self.assertEqual(find(screen, cal, scale).target[1], Y0)
        self.check_scales(run)

    def test_refuses_when_there_is_no_reconnect_button(self):
        def run(scale, cal):
            screen = Screen([(Y0, "Back to Server List"), (Y0 + 24 * scale, "Quit Game")], scale, CX)
            found = find(screen, cal, scale)
            self.assertIsNone(found.target)
            self.assertEqual(found.button_count, 2)
        self.check_scales(run)

    def test_refuses_a_single_unrelated_button(self):
        def run(scale, cal):
            screen = Screen([(Y0, "Back to Title Screen")], scale, CX)
            self.assertIsNone(find(screen, cal, scale).target)
        self.check_scales(run)

    def test_refuses_two_lookalike_candidates(self):
        def run(scale, cal):
            screen = Screen([(Y0, "Reconnect"), (Y0 + 24 * scale, "Reconnect")], scale, CX)
            self.assertIsNone(find(screen, cal, scale).target)
        self.check_scales(run)

    def test_refuses_a_screen_with_no_buttons_at_all(self):
        cal = calibrate(2)
        blank = Screen([(5000, "Offscreen")], 2, CX)
        found = find(blank, cal, 2)
        self.assertIsNone(found.target)
        self.assertTrue(found.used_fallback)


class ScaleMeasurementTest(unittest.TestCase):
    def test_measures_every_gui_scale(self):
        for scale in (1, 2, 3, 4):
            with self.subTest(scale=scale):
                screen = Screen([(Y0, "Reconnect"), (Y0 + 24 * scale, "Back to Server List")], scale, CX, hovered=0)
                measured, face, height = vision.measure_scale(screen.pixel, CX, Y0, 14)
                self.assertEqual(measured, scale)
                self.assertEqual(face, (90, 108, 154))
                self.assertEqual(height, 18 * scale + 1)
                self.assertTrue(vision.plausible_button(screen.pixel, CX, Y0, face, measured, 14))

    def test_a_point_on_plain_background_is_not_a_button(self):
        screen = Screen([(Y0, "Reconnect")], 2, CX)
        scale, face, _ = vision.measure_scale(screen.pixel, 20, 20, 14)
        self.assertFalse(vision.plausible_button(screen.pixel, 20, 20, face, scale, 14))

    def test_an_off_centre_hover_still_counts(self):
        screen = Screen([(Y0, "Reconnect")], 3, CX, hovered=0)
        scale, face, _ = vision.measure_scale(screen.pixel, CX + 60, Y0, 14)
        self.assertEqual(scale, 3)
        self.assertTrue(vision.plausible_button(screen.pixel, CX + 60, Y0, face, scale, 14))


if __name__ == "__main__":
    unittest.main()
