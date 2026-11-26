"""Settings and calibration, stored as JSON under %APPDATA%."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Optional

from .monitor import MonitorSettings


def default_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "AegisAfkWatch"


def default_config_path() -> Path:
    return default_dir() / "reconnect.json"


def default_log_path() -> Path:
    return default_dir() / "reconnect.log"


@dataclass
class Calibration:
    """Where the Reconnect button is, and what it looks like, recorded once by `calibrate`."""

    offset_x: int  # button centre minus window-client centre, in pixels
    offset_y: int
    idle: list[list[int]]   # colours with the mouse elsewhere
    hover: list[list[int]]  # colours with the mouse over the button
    scale: int = 1          # GUI scale: a button is 20 * scale pixels tall
    buttons_seen: int = 0   # how many buttons the calibration screen had (information only)
    rank_from_top: int = 0  # which of them was Reconnect (information only)


@dataclass
class Config:
    # --- finding the game ---
    server_port: int = 25565  # 0 means "any established connection that is not 80 or 443"
    process_names: list[str] = field(default_factory=lambda: ["javaw", "java"])
    window_title: str = "Minecraft"

    # --- watching the internet ---
    internet_targets: list[list] = field(default_factory=lambda: [["1.1.1.1", 443], ["8.8.8.8", 53]])
    poll_seconds: float = 5.0
    outage_after_failures: int = 3
    stable_seconds: float = 10.0
    grace_seconds: float = 60.0

    # --- recovering ---
    max_attempts: int = 3
    connect_timeout_seconds: float = 60.0
    join_delay_seconds: float = 10.0
    min_idle_seconds: float = 15.0  # wait until you have stopped using the PC; 0 disables
    chat_key: str = "T"
    join_command: str = "/joinq AFK"
    beep: bool = False

    # --- telling crashes apart ---
    # A drop while the internet is fine is a kick, ban or restart. Only a restart (the server stopped
    # answering and came back) is reconnected automatically. Turn this on to also reconnect when the server
    # never stopped answering. Careful: that includes being kicked.
    reconnect_on_unknown_drop: bool = False
    unknown_drop_seconds: float = 20.0
    hung_seconds: float = 20.0           # report a window that has not responded for this long
    crash_idle_seconds: float = 60.0     # a vanished game counts as a probable crash if you were idle this long

    # --- recognising the button ---
    colour_tolerance: int = 40
    face_tolerance: int = 14
    min_match: float = 0.9
    match_margin: float = 0.08   # with several buttons, the best must beat the runner-up by this much
    gui_scale: int = 0           # 0 = use the calibrated value
    calibration: Optional[Calibration] = None

    def monitor_settings(self) -> MonitorSettings:
        return MonitorSettings(
            outage_after_failures=self.outage_after_failures,
            stable_seconds=self.stable_seconds,
            grace_seconds=self.grace_seconds,
            unknown_drop_seconds=self.unknown_drop_seconds,
            reconnect_on_unknown=self.reconnect_on_unknown_drop,
            hung_seconds=self.hung_seconds,
        )


def load(path: Path) -> Config:
    if not path.exists():
        return Config()
    data = json.loads(path.read_text(encoding="utf-8"))
    known = {f.name for f in fields(Config)}
    values = {k: v for k, v in data.items() if k in known and k != "calibration"}
    cfg = Config(**values)
    cal = data.get("calibration")
    if cal:
        cfg.calibration = Calibration(
            offset_x=int(cal["offset_x"]),
            offset_y=int(cal["offset_y"]),
            idle=[list(map(int, p)) for p in cal["idle"]],
            hover=[list(map(int, p)) for p in cal["hover"]],
            scale=int(cal.get("scale", 1)),
            buttons_seen=int(cal.get("buttons_seen", 0)),
            rank_from_top=int(cal.get("rank_from_top", 0)),
        )
    return cfg


def save(cfg: Config, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
