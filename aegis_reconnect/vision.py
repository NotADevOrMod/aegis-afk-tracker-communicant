"""Finding the Reconnect button on a disconnect screen that may have one, two or three buttons."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import signature
from .config import Calibration
from .signature import Sampler

_FACE_COLUMNS_UNITS = (-70, -50, 50, 70)  # either side of the label, so text never hides the face
PITCH_UNITS = 24                          # distance between stacked buttons
SCAN_PITCHES = 6                          # how far up and down to look for the other buttons


@dataclass(frozen=True)
class Finding:
    target: Optional[tuple[int, int, float]]  # (x, y, ratio) of the button to click, or None
    centers: list[int]                        # y of every button found, top to bottom
    ratios: list[float]                       # how well each matches "Reconnect"
    used_fallback: bool = False

    @property
    def button_count(self) -> int:
        return len(self.centers)

    @property
    def rank_from_top(self) -> Optional[int]:
        if self.target is None or self.target[1] not in self.centers:
            return None
        return self.centers.index(self.target[1]) + 1


def find_reconnect(
    pixel: Sampler,
    cal: Calibration,
    scale: int,
    x: int,
    y: int,
    top: int,
    bottom: int,
    *,
    tolerance: int,
    face_tolerance: int,
    min_ratio: float,
    margin: float,
) -> Finding:
    """
    (x, y) is where the button was calibrated. The screen is scanned for button faces near there; each one
    is compared with the Reconnect signature; the click target is chosen only if one clearly wins.
    """
    faces = [signature.dominant_colour(cal.idle), signature.dominant_colour(cal.hover)]
    columns = [x + dx * scale for dx in _FACE_COLUMNS_UNITS]

    def is_face(py: int) -> bool:
        return any(signature.near(pixel(c, py), face, face_tolerance) for c in columns for face in faces)

    reach = SCAN_PITCHES * PITCH_UNITS * scale
    bands = signature.find_bands(
        is_face,
        max(top, y - reach),
        min(bottom, y + reach),
        min_run=int(10 * scale),
        merge_gap=3 * scale,
    )
    centers = [(a + b) // 2 for a, b in bands]
    offsets = signature.offsets_for(scale)
    references = [cal.idle, cal.hover]

    if centers:
        ev = signature.evaluate(pixel, references, x, centers, offsets, tolerance)
        chosen = signature.decide(ev, min_ratio, margin)
        target = (x, chosen[0], chosen[1]) if chosen else None
        return Finding(target, ev.centers, ev.ratios)

    fallback = signature.locate(pixel, references, x, y, offsets, tolerance, min_ratio, search=reach)
    target = (x, fallback[0], fallback[1]) if fallback else None
    return Finding(target, [], [], used_fallback=True)


def measure_scale(pixel: Sampler, x: int, y: int, face_tolerance: int) -> tuple[int, signature.Rgb, int]:
    """
    From a point on a button, work out the GUI scale. Returns (scale, face colour, face height in pixels);
    a height of 0 means the point was not on a button.
    """
    coarse = [(dx, dy) for dy in range(-7, 8, 2) for dx in range(-90, 91, 6)]
    face = signature.dominant_colour(signature.sample(pixel, x, y, coarse))
    height = signature.face_height(pixel, x, y, face, face_tolerance)
    return signature.estimate_scale(height), face, height


def plausible_button(pixel: Sampler, x: int, y: int, face: signature.Rgb, scale: int, tolerance: int) -> bool:
    """
    Sanity check for calibration: is the face colour at (x, y) really a button, about 200 GUI units wide,
    rather than the cursor resting on a wall of background? Measured on a row just above the label so no
    text interrupts it.
    """
    row = y - 6 * scale
    if not signature.near(pixel(x, row), face, tolerance):
        return False
    limit = 260 * scale
    left = 0
    while left < limit and signature.near(pixel(x - left - 1, row), face, tolerance):
        left += 1
    right = 0
    while right < limit and signature.near(pixel(x + right + 1, row), face, tolerance):
        right += 1
    return 150 * scale <= left + right + 1 <= 215 * scale
