"""
Recognising a button by what it looks like. Pure logic: the caller supplies a function that reads one pixel.

A "signature" is the colours at a grid of points on the button face and its label. Every button has the
same face, so the label is what tells "Reconnect" from "Back to Server List"; the grid is dense across the
label for that reason.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

Rgb = tuple[int, int, int]
Sampler = Callable[[int, int], Rgb]

# Offsets in GUI units (a button is 200 x 20 units); multiplied by the GUI scale to get pixels.
_DX = tuple(range(-48, 49, 6))
_DY = (-5, -3, -1, 1, 3, 5)
BUTTON_HEIGHT_UNITS = 20
FACE_UNITS = 16.5  # the flat face is a little shorter than the full button


def offsets_for(scale: int) -> list[tuple[int, int]]:
    return [(dx * scale, dy * scale) for dy in _DY for dx in _DX]


def sample(sampler: Sampler, x: int, y: int, offsets: Sequence[tuple[int, int]]) -> list[Rgb]:
    return [sampler(x + dx, y + dy) for dx, dy in offsets]


def near(a: Sequence[int], b: Sequence[int], tolerance: int) -> bool:
    return all(abs(a[i] - b[i]) <= tolerance for i in range(3))


def match_ratio(current: Sequence[Rgb], reference: Sequence[Sequence[int]], tolerance: int) -> float:
    """Fraction of points whose colour is within `tolerance` on every channel."""
    if not reference or len(current) != len(reference):
        return 0.0
    return sum(1 for c, r in zip(current, reference) if near(c, r, tolerance)) / len(reference)


def dominant_colour(samples: Sequence[Sequence[int]]) -> Rgb:
    """The most common colour: on a button, that is the face."""
    (r, g, b), _ = Counter(tuple(s) for s in samples).most_common(1)[0]
    return (r, g, b)


def face_height(sampler: Sampler, x: int, y: int, face: Rgb, tolerance: int, limit: int = 240) -> int:
    """
    Pixel height of the flat face at (x, y). Tries columns left and right of the label, because glyph
    pixels interrupt the run in the middle, and keeps the tallest.
    """
    best = 0
    for dx in range(-500, 501, 10):
        col = x + dx
        if not near(sampler(col, y), face, tolerance):
            continue
        up = 0
        while up < limit and near(sampler(col, y - up - 1), face, tolerance):
            up += 1
        down = 0
        while down < limit and near(sampler(col, y + down + 1), face, tolerance):
            down += 1
        best = max(best, up + down + 1)
    return best


def estimate_scale(face_pixels: int) -> int:
    return max(1, round(face_pixels / FACE_UNITS))


def find_bands(is_face: Callable[[int], bool], y_from: int, y_to: int, min_run: int, merge_gap: int) -> list[tuple[int, int]]:
    """Vertical runs of face colour, i.e. where the buttons are. Small gaps (borders, noise) are bridged."""
    runs: list[list[int]] = []
    start: Optional[int] = None
    for y in range(y_from, y_to + 1):
        if is_face(y):
            if start is None:
                start = y
        elif start is not None:
            runs.append([start, y - 1])
            start = None
    if start is not None:
        runs.append([start, y_to])

    merged: list[list[int]] = []
    for run in runs:
        if merged and run[0] - merged[-1][1] <= merge_gap:
            merged[-1][1] = run[1]
        else:
            merged.append(run)
    return [(a, b) for a, b in merged if b - a + 1 >= min_run]


@dataclass(frozen=True)
class Evaluation:
    centers: list[int]
    ratios: list[float]


def evaluate(
    sampler: Sampler,
    references: Sequence[Sequence[Sequence[int]]],
    x: int,
    centers: Sequence[int],
    offsets: Sequence[tuple[int, int]],
    tolerance: int,
) -> Evaluation:
    """How closely each candidate button matches the Reconnect signature (best of its idle and hover looks)."""
    ratios = []
    for cy in centers:
        current = sample(sampler, x, cy, offsets)
        ratios.append(max(match_ratio(current, ref, tolerance) for ref in references))
    return Evaluation(list(centers), ratios)


def decide(ev: Evaluation, min_ratio: float, margin: float) -> Optional[tuple[int, float]]:
    """
    The (y, ratio) of the Reconnect button, or None. It must match well, and with several buttons on screen
    it must clearly beat the runner-up; two lookalikes mean "not sure", and not being sure means no click.
    """
    if not ev.centers:
        return None
    ranked = sorted(zip(ev.ratios, ev.centers), reverse=True)
    best_ratio, best_y = ranked[0]
    if best_ratio < min_ratio:
        return None
    if len(ranked) > 1 and best_ratio - ranked[1][0] < margin:
        return None
    return best_y, best_ratio


def locate(
    sampler: Sampler,
    references: Sequence[Sequence[Sequence[int]]],
    x: int,
    y: int,
    offsets: Sequence[tuple[int, int]],
    tolerance: int,
    min_ratio: float,
    search: int,
    step: int = 2,
) -> Optional[tuple[int, float]]:
    """Fallback when no button bands can be found: slide the signature up and down and take the best fit."""
    best: Optional[tuple[int, float]] = None
    for shift in range(-search, search + 1, step):
        cy = y + shift
        current = sample(sampler, x, cy, offsets)
        ratio = max(match_ratio(current, ref, tolerance) for ref in references)
        if best is None or ratio > best[1]:
            best = (cy, ratio)
    return best if best is not None and best[1] >= min_ratio else None
