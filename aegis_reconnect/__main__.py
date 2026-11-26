"""Command line: run (default), calibrate, check."""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import sys
import time
from pathlib import Path

from . import __version__, config, vision, winapi
from .crash import classify
from .game import (collect_crash_files, find_game, game_dirs, internet_ok, remote_server, server_reachable)
from .monitor import Event, Monitor, Observation, Occurrence
from .reconnector import Reconnector

log = logging.getLogger("aegis_reconnect")

MAX_LOG_BYTES = 512 * 1024
MISSING_GAME_HINT_AFTER_SECONDS = 30


def _setup_logging() -> None:
    log.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(asctime)s] %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    log.addHandler(console)
    path = config.default_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(path, maxBytes=MAX_LOG_BYTES, backupCount=1, encoding="utf-8")
    file_handler.setFormatter(formatter)
    log.addHandler(file_handler)


def _run(cfg: config.Config, dry_run: bool) -> int:
    monitor = Monitor(cfg.monitor_settings())
    reconnector = Reconnector(cfg, dry_run)

    log.info("AEGIS Reconnect %s started. Server port %s.%s", __version__,
             cfg.server_port or "any", " DRY RUN: nothing will be clicked or typed." if dry_run else "")
    if cfg.calibration is None:
        log.warning("Not calibrated yet. It will watch and report, but cannot click. Run: AegisReconnect.exe calibrate")
    if cfg.reconnect_on_unknown_drop:
        log.warning("reconnect_on_unknown_drop is ON: it will also reconnect after drops it cannot explain, "
                    "which includes being kicked.")

    started = time.monotonic()
    warned_missing = False
    known_pid = None
    folders: list[Path] = []
    last_addr = None
    last_idle = 0.0

    while True:
        try:
            game = find_game(cfg)
            if game is None and not warned_missing and time.monotonic() - started > MISSING_GAME_HINT_AFTER_SECONDS:
                warned_missing = True
                log.warning("Cannot find the game window yet (looking for a %s process whose title contains %r). "
                            "If the game is running, adjust process_names or window_title in %s.",
                            "/".join(cfg.process_names), cfg.window_title, config.default_config_path())

            if game is not None and game.pid != known_pid:
                known_pid = game.pid
                folders = game_dirs(game.pid)
                last_addr = None

            address = remote_server(game.pid, cfg.server_port) if game is not None else None
            connected = address is not None
            if address is not None:
                last_addr = address
            reachable = None
            if game is not None and not connected and last_addr is not None:
                reachable = server_reachable(last_addr)

            observation = Observation(
                now=time.monotonic(),
                internet=internet_ok(cfg.internet_targets),
                game_running=game is not None,
                game_connected=connected,
                server_reachable=reachable,
                game_hung=game is not None and winapi.is_hung(game.hwnd),
            )
            for item in monitor.update(observation):
                _handle(item, game, reconnector, cfg, folders, last_idle)

            if game is None:
                known_pid = None
            last_idle = winapi.idle_seconds()
        except Exception:  # a monitoring hiccup must never end the watch
            log.exception("Unexpected error; carrying on.")
        time.sleep(cfg.poll_seconds)


def _handle(item: Occurrence, game, reconnector: Reconnector, cfg: config.Config, folders, idle_before: float) -> None:
    detail = f" ({item.detail})" if item.detail else ""
    event = item.event

    if event is Event.GAME_STARTED:
        log.info("Found the game.")
    elif event is Event.GAME_STOPPED:
        verdict = classify(time.time(), collect_crash_files(folders), idle_before, cfg.crash_idle_seconds)
        if verdict.is_crash:
            reconnector.alert(f"The game crashed: {verdict.detail}. I cannot restart it for you; "
                              "start it and rejoin by hand.")
        else:
            log.info("The game closed. %s.", verdict.detail)
    elif event is Event.GAME_FROZEN:
        reconnector.alert(f"The game window is not responding{detail}. I cannot fix a frozen game.")
    elif event is Event.OUTAGE_STARTED:
        log.warning("Internet outage detected%s.", detail)
    elif event is Event.INTERNET_RESTORED:
        log.info("Internet is back%s.", detail)
    elif event is Event.GAME_SURVIVED:
        log.info("The game stayed connected through the outage. Nothing to do.")
    elif event is Event.DISCONNECTED_ONLINE:
        log.warning("The game lost its server connection while the internet is fine%s.", detail)
    elif event is Event.SERVER_DOWN:
        log.warning("The server stopped answering. Waiting for it to come back.")
    elif event is Event.SERVER_BACK:
        log.info("The server is answering again.")
    elif event is Event.DROP_NOT_ACTED:
        reconnector.alert(f"Not reconnecting: {item.detail}.")
    elif event is Event.RECONNECT_NEEDED and game is not None:
        reconnector.recover(game, item.reason)


def _check(cfg: config.Config) -> int:
    """Reports what the disconnect screen looks like right now and whether it would click. Sends no input."""
    game = find_game(cfg)
    if game is None:
        print("The game is not running.")
        return 1
    cal = cfg.calibration
    if cal is None:
        print("Not calibrated. Run: AegisReconnect.exe calibrate")
        return 1

    scale = cfg.gui_scale or cal.scale
    area = winapi.client_area(game.hwnd)
    center_x, center_y = area.center
    with winapi.ScreenSampler() as screen:
        finding = vision.find_reconnect(
            screen.pixel, cal, scale, center_x + cal.offset_x, center_y + cal.offset_y,
            area.top, area.top + area.height,
            tolerance=cfg.colour_tolerance, face_tolerance=cfg.face_tolerance,
            min_ratio=cfg.min_match, margin=cfg.match_margin,
        )

    print(f"Calibrated with {cal.buttons_seen or '?'} button(s), Reconnect #{cal.rank_from_top or '?'}, GUI scale {scale}.")
    if finding.used_fallback:
        print("No buttons found by colour; used the direct search.")
    else:
        shown = ", ".join(f"#{i + 1}: {r:.0%}" for i, r in enumerate(finding.ratios))
        print(f"Buttons on screen now: {finding.button_count}. Match for Reconnect, top to bottom: {shown or 'none'}.")
    if finding.target is None:
        print(f"Would NOT click (needs {cfg.min_match:.0%}, and a {cfg.match_margin:.0%} lead over any other button).")
        return 1
    x, y, ratio = finding.target
    print(f"WOULD CLICK at ({x}, {y}), match {ratio:.0%}"
          + (f", the #{finding.rank_from_top} button from the top." if finding.rank_from_top else "."))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="AegisReconnect", description=__doc__)
    parser.add_argument("command", nargs="?", choices=["run", "calibrate", "check"], default="run")
    parser.add_argument("--config", type=Path, default=config.default_config_path())
    parser.add_argument("--dry-run", action="store_true", help="log what would happen; click and type nothing")
    args = parser.parse_args()

    winapi.make_dpi_aware()
    _setup_logging()
    cfg = config.load(args.config)

    if args.command == "calibrate":
        from . import calibrate
        return calibrate.run(cfg, args.config)
    if args.command == "check":
        return _check(cfg)
    return _run(cfg, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
