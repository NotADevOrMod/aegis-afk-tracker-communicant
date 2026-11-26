"""A fake disconnect screen: stacked 200x20-unit buttons with different labels, drawn pixel by pixel."""

import zlib

FACE = (111, 111, 111)
HOVER = (90, 108, 154)
BORDER = (40, 40, 40)
BACKGROUND = (30, 30, 30)
TEXT = (255, 255, 255)


def _glyph(label: str, ux: int, uy: int) -> bool:
    """About 14% of label pixels are text, in a pattern unique to the label."""
    return (zlib.crc32(label.encode()) + ux * 17 + uy * 7) % 7 == 0


class Screen:
    def __init__(self, buttons, scale=1, cx=500, hovered=None):
        """buttons: list of (centre_y_pixels, label)."""
        self.buttons = buttons
        self.scale = scale
        self.cx = cx
        self.hovered = hovered

    def pixel(self, x, y):
        s = self.scale
        for index, (cy, label) in enumerate(self.buttons):
            ux = (x - self.cx) // s
            uy = (y - cy) // s
            if abs(x - self.cx) <= 100 * s and abs(y - cy) <= 10 * s:
                if abs(y - cy) > 10 * s - s:
                    return BORDER
                if -48 <= ux <= 48 and -5 <= uy <= 5 and _glyph(label, ux, uy):
                    return TEXT
                return HOVER if self.hovered == index else FACE
        # the error message above the buttons: sparse white text on the background
        if (x * 13 + y * 7) % 11 == 0 and y < min(cy for cy, _ in self.buttons) - 20 * s:
            return TEXT
        return BACKGROUND
