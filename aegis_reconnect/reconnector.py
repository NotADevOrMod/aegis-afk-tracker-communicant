"""
Gets back into the game after an outage: clicks Reconnect only when it can see the button, confirms the
connection really came back, then types the join command. Every input is preceded by a check that the game
window is the one in front.
"""

from __future__ import annotations

import logging
import time

from . import vision, winapi
from .config import Config
from .game import GameWindow, remote_server
from .monitor import Reason

log = logging.getLogger("aegis_reconnect")

QUIET_WAIT_LIMIT_SECONDS = 300
FOCUS_SETTLE_SECONDS = 0.5
CHAT_OPEN_SECONDS = 0.4


class Reconnector:
    def __init__(self, cfg: Config, dry_run: bool) -> None:
        self._cfg = cfg
        self._dry_run = dry_run

    def alert(self, message: str) -> None:
        log.warning(message)
        if self._cfg.beep:
            winapi.beep()

    def recover(self, game: GameWindow, reason: Reason | None = None) -> bool:
        cfg = self._cfg
        log.info("Recovering from: %s.", reason.value if reason else "unspecified cause")
        if cfg.calibration is None and not self._dry_run:
            self.alert("Not calibrated, so I will not guess where the button is. Run: AegisReconnect.exe calibrate")
            return False

        for attempt in range(1, cfg.max_attempts + 1):
            log.info("Reconnect attempt %d of %d.", attempt, cfg.max_attempts)

            if self._wait_for_quiet_user() and self._click_reconnect(game):
                if self._dry_run:
                    log.info("[dry run] stopping here; nothing was clicked or typed.")
                    return True
                if self._wait_connected(game):
                    log.info("Server connection is back.")
                    time.sleep(cfg.join_delay_seconds)
                    if self._send_join_command(game):
                        log.info("Sent %r. Check that you are in the queue.", cfg.join_command)
                    else:
                        self.alert("Reconnected, but could not send the join command. Run it yourself.")
                    return True
                log.warning("No server connection after %.0f s.", cfg.connect_timeout_seconds)

            if attempt < cfg.max_attempts:
                backoff = 15 * 2 ** (attempt - 1)
                log.info("Waiting %d s before trying again.", backoff)
                time.sleep(backoff)

        self.alert(f"Gave up after {cfg.max_attempts} attempts. Reconnect by hand.")
        return False

    # --- steps ------------------------------------------------------------------------------------

    def _wait_for_quiet_user(self) -> bool:
        if self._cfg.min_idle_seconds <= 0:
            return True
        deadline = time.monotonic() + QUIET_WAIT_LIMIT_SECONDS
        while time.monotonic() < deadline:
            if winapi.idle_seconds() >= self._cfg.min_idle_seconds:
                return True
            time.sleep(2)
        log.warning("You kept using the computer for %d s; not taking over.", QUIET_WAIT_LIMIT_SECONDS)
        return False

    def _ensure_in_front(self, game: GameWindow) -> bool:
        winapi.bring_to_front(game.hwnd)
        time.sleep(FOCUS_SETTLE_SECONDS)
        if winapi.foreground_pid() != game.pid:
            log.warning("The game window is not in front; not sending input.")
            return False
        return True

    def _click_reconnect(self, game: GameWindow) -> bool:
        cfg = self._cfg
        cal = cfg.calibration
        if cal is None:
            log.info("[dry run] not calibrated, so no button search is possible.")
            return True

        if not self._dry_run and not self._ensure_in_front(game):
            return False

        scale = cfg.gui_scale or cal.scale
        area = winapi.client_area(game.hwnd)
        center_x, center_y = area.center
        with winapi.ScreenSampler() as screen:
            finding = vision.find_reconnect(
                screen.pixel, cal, scale,
                center_x + cal.offset_x, center_y + cal.offset_y,
                area.top, area.top + area.height,
                tolerance=cfg.colour_tolerance, face_tolerance=cfg.face_tolerance,
                min_ratio=cfg.min_match, margin=cfg.match_margin,
            )

        describe_finding(finding)
        if finding.target is None:
            log.warning("Not clicking: no button clearly looks like Reconnect. The screen may not be a "
                        "disconnect screen, may have no Reconnect button, or the calibration is out of date.")
            return False

        x, y, ratio = finding.target
        if self._dry_run:
            log.info("[dry run] would click Reconnect at (%d, %d), match %.0f%%.", x, y, ratio * 100)
            return True
        log.info("Clicking Reconnect at (%d, %d), match %.0f%%.", x, y, ratio * 100)
        winapi.click(x, y)
        return True

    def _wait_connected(self, game: GameWindow) -> bool:
        deadline = time.monotonic() + self._cfg.connect_timeout_seconds
        while time.monotonic() < deadline:
            if remote_server(game.pid, self._cfg.server_port) is not None:
                return True
            time.sleep(1)
        return False

    def _send_join_command(self, game: GameWindow) -> bool:
        cfg = self._cfg
        if not self._ensure_in_front(game):
            return False
        winapi.tap_key(winapi.vk_for(cfg.chat_key))
        time.sleep(CHAT_OPEN_SECONDS)

        if not self._ensure_in_front(game):
            return False
        winapi.type_text(cfg.join_command)
        time.sleep(0.2)

        if not self._ensure_in_front(game):
            return False
        winapi.tap_key(winapi.VK_RETURN)
        return True


def describe_finding(finding: vision.Finding) -> None:
    """Log what is on the disconnect screen: how many buttons, and how Reconnect-like each one is."""
    if finding.used_fallback:
        log.info("Could not pick out the buttons by colour; searched for the Reconnect look directly.")
        return
    shown = ", ".join(f"#{i + 1}: {r:.0%}" for i, r in enumerate(finding.ratios))
    log.info("The screen has %d button%s. Match for Reconnect, top to bottom: %s.",
             finding.button_count, "" if finding.button_count == 1 else "s", shown or "none")
