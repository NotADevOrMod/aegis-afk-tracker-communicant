"""Telling a crash from a normal exit once the game process has gone. Pure logic."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Sequence


class CrashKind(Enum):
    JAVA_CRASH = auto()      # Minecraft wrote a crash report
    NATIVE_CRASH = auto()    # the JVM itself died (hs_err log)
    VANISHED_IDLE = auto()   # gone with no evidence, while nobody was at the keyboard
    CLEAN_EXIT = auto()


@dataclass(frozen=True)
class CrashFile:
    name: str
    modified: float  # epoch seconds


@dataclass(frozen=True)
class Verdict:
    kind: CrashKind
    detail: str = ""

    @property
    def is_crash(self) -> bool:
        return self.kind is not CrashKind.CLEAN_EXIT


def classify(
    stopped_at: float,
    files: Sequence[CrashFile],
    idle_seconds_at_stop: float,
    idle_threshold: float,
    window: float = 120.0,
) -> Verdict:
    """
    `stopped_at` is when the process was noticed missing. A crash report or hs_err log written shortly before
    that is strong evidence. With none, a game that vanished while the user was away is still suspicious,
    whereas one that closed while the user was at the keyboard was almost certainly closed on purpose.
    """
    recent = [f for f in files if stopped_at - window <= f.modified <= stopped_at + 30]
    native = [f for f in recent if f.name.startswith("hs_err_pid")]
    java = [f for f in recent if f.name.startswith("crash-")]
    if native:
        return Verdict(CrashKind.NATIVE_CRASH, f"JVM crash log {max(native, key=lambda f: f.modified).name}")
    if java:
        return Verdict(CrashKind.JAVA_CRASH, f"crash report {max(java, key=lambda f: f.modified).name}")
    if idle_seconds_at_stop >= idle_threshold:
        return Verdict(CrashKind.VANISHED_IDLE,
                       f"no crash file, but nobody had touched the computer for {int(idle_seconds_at_stop)}s")
    return Verdict(CrashKind.CLEAN_EXIT, "no crash evidence; closed normally")
