"""
One-time setup: record where the Reconnect button is and what it looks like, so the tool can recognise it
later instead of guessing. Works on screens with one, two or three buttons.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from . import config, signature, vision, winapi
from .config import Calibration, Config
from .game import find_game

log = logging.getLogger("aegis_reconnect")


def _wait_for_f8() -> None:
    while winapi.key_down(winapi.VK_F8):
        time.sleep(0.05)  # let go of any earlier press
    while not winapi.key_down(winapi.VK_F8):
        time.sleep(0.05)
    while winapi.key_down(winapi.VK_F8):
        time.sleep(0.05)


def run(cfg: Config, path: Path) -> int:
    game = find_game(cfg)
    if game is None:
        print("The game is not running (or its window title does not contain "
              f"{cfg.window_title!r}). Start it, then run this again.")
        return 1

    print("Calibration")
    print("-----------")
    print("1. Make the game show its Disconnected screen (for example, turn Wi-Fi off for about 40 seconds).")
    print("2. Move your mouse over the Reconnect button and press F8.")
    _wait_for_f8()

    area = winapi.client_area(game.hwnd)
    mouse_x, mouse_y = winapi.cursor_pos()
    center_x, center_y = area.center

    with winapi.ScreenSampler() as screen:
        scale, face, height = vision.measure_scale(screen.pixel, mouse_x, mouse_y, cfg.face_tolerance)
        if height < 8 or not vision.plausible_button(screen.pixel, mouse_x, mouse_y, face, scale, cfg.face_tolerance):
            print("   That does not look like a button. Is the mouse exactly over Reconnect and the game window "
                  "in front? Run calibrate again.")
            return 1
        if cfg.gui_scale:
            scale = cfg.gui_scale
        hover = signature.sample(screen.pixel, mouse_x, mouse_y, signature.offsets_for(scale))
    print(f"   Got it. GUI scale looks like {scale} (button face {height}px tall). "
          "If that is wrong, set gui_scale in reconnect.json.")

    print("3. Now move the mouse OFF the button (anywhere else on the game) and press F8 again.")
    _wait_for_f8()
    with winapi.ScreenSampler() as screen:
        idle = signature.sample(screen.pixel, mouse_x, mouse_y, signature.offsets_for(scale))

    cal = Calibration(
        offset_x=mouse_x - center_x,
        offset_y=mouse_y - center_y,
        idle=[list(p) for p in idle],
        hover=[list(p) for p in hover],
        scale=scale,
    )

    with winapi.ScreenSampler() as screen:
        finding = vision.find_reconnect(
            screen.pixel, cal, scale, mouse_x, mouse_y, area.top, area.top + area.height,
            tolerance=cfg.colour_tolerance, face_tolerance=cfg.face_tolerance,
            min_ratio=cfg.min_match, margin=cfg.match_margin,
        )
    if finding.centers:
        cal.buttons_seen = finding.button_count
        cal.rank_from_top = min(range(len(finding.centers)), key=lambda i: abs(finding.centers[i] - mouse_y)) + 1
        print(f"   I can see {cal.buttons_seen} button{'s' if cal.buttons_seen != 1 else ''} on this screen; "
              f"Reconnect is #{cal.rank_from_top} from the top.")
    else:
        print("   I could not pick out the individual buttons by colour (a resource pack?). I will fall back to "
              "searching for the Reconnect look directly, which is less precise.")

    cfg.calibration = cal
    config.save(cfg, path)
    print(f"Saved to {path}.")
    print("The number of buttons can change from one crash to the next; that is fine, it finds Reconnect by "
          "its label, not its position.")
    print("Check it any time a Disconnected screen is showing with:  AegisReconnect.exe check")
    return 0
