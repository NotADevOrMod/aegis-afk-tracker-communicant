"""Decides what a lost connection means. Pure logic: no Windows, no network, no clock of its own."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class Reason(Enum):
    NETWORK = "network outage"
    SERVER = "server restart"
    UNKNOWN = "unexplained disconnect"


class Event(Enum):
    GAME_STARTED = auto()
    GAME_STOPPED = auto()
    GAME_FROZEN = auto()
    OUTAGE_STARTED = auto()
    INTERNET_RESTORED = auto()
    GAME_SURVIVED = auto()
    DISCONNECTED_ONLINE = auto()
    SERVER_DOWN = auto()
    SERVER_BACK = auto()
    RECONNECT_NEEDED = auto()
    DROP_NOT_ACTED = auto()


@dataclass(frozen=True)
class Occurrence:
    event: Event
    detail: str = ""
    reason: Optional[Reason] = None


@dataclass(frozen=True)
class Observation:
    now: float
    internet: bool
    game_running: bool
    game_connected: bool
    # None when it was not checked (or the server's address is not known yet).
    server_reachable: Optional[bool] = None
    game_hung: bool = False


@dataclass(frozen=True)
class MonitorSettings:
    outage_after_failures: int = 3
    stable_seconds: float = 10.0
    grace_seconds: float = 60.0
    # The game must have been connected this recently when an outage was declared.
    recent_connection_seconds: float = 60.0
    # Server-side crash detection.
    server_down_failures: int = 2
    unknown_drop_seconds: float = 20.0
    reconnect_on_unknown: bool = False
    hung_seconds: float = 20.0


class Monitor:
    """
    Feed it one Observation per poll. It reports what happened and, when a reconnect is justified, why.

    A reconnect is asked for in exactly two situations:
      * NETWORK: the internet went down while the game was connected, came back, and the game lost its
        server connection.
      * SERVER: the game lost its connection while the internet was fine, the server then stopped answering
        and has now come back (a crash or restart).
    A drop where the server never stopped answering looks like a kick, a ban or a client-side error. That is
    reported (DROP_NOT_ACTED) and left alone unless `reconnect_on_unknown` is switched on.
    """

    def __init__(self, settings: MonitorSettings) -> None:
        self._s = settings
        self._internet_up = True
        self._failures = 0
        self._stable_since: Optional[float] = None
        self._outage_start: Optional[float] = None
        self._last_connected_at: Optional[float] = None
        self._connected_before_outage = False
        self._recovered_at = 0.0
        self._pending = False
        self._was_connected = False
        self._game_seen = False
        self._hung_since: Optional[float] = None
        self._hung_reported = False
        # server watch (a drop while the internet is fine)
        self._watching = False
        self._drop_at = 0.0
        self._server_failures = 0
        self._server_down = False
        self._server_stable_since: Optional[float] = None

    def update(self, obs: Observation) -> list[Occurrence]:
        out: list[Occurrence] = []
        now = obs.now

        self._track_game(obs, out)
        self._track_frozen(obs, out)

        if obs.game_connected:
            self._last_connected_at = now
            self._watching = False  # connected again (perhaps by hand): nothing left to watch

        self._track_internet(obs, out)
        self._track_network_recovery(obs, out)
        self._track_server_drop(obs, out)

        self._was_connected = obs.game_connected
        return out

    # --- parts ------------------------------------------------------------------------------------

    def _track_game(self, obs: Observation, out: list[Occurrence]) -> None:
        if obs.game_running and not self._game_seen:
            self._game_seen = True
            out.append(Occurrence(Event.GAME_STARTED))
        if not obs.game_running and self._game_seen:
            self._game_seen = False
            self._pending = False
            self._watching = False
            out.append(Occurrence(Event.GAME_STOPPED))

    def _track_frozen(self, obs: Observation, out: list[Occurrence]) -> None:
        if obs.game_running and obs.game_hung:
            if self._hung_since is None:
                self._hung_since = obs.now
            elif not self._hung_reported and obs.now - self._hung_since >= self._s.hung_seconds:
                self._hung_reported = True
                out.append(Occurrence(Event.GAME_FROZEN, f"not responding for {int(obs.now - self._hung_since)}s"))
        else:
            self._hung_since = None
            self._hung_reported = False

    def _track_internet(self, obs: Observation, out: list[Occurrence]) -> None:
        now = obs.now
        if not obs.internet:
            self._stable_since = None
            self._failures += 1
            if self._internet_up and self._failures >= self._s.outage_after_failures:
                self._internet_up = False
                self._outage_start = now
                self._pending = False
                self._watching = False
                self._connected_before_outage = (
                    self._last_connected_at is not None
                    and now - self._last_connected_at <= self._s.recent_connection_seconds
                )
                out.append(Occurrence(Event.OUTAGE_STARTED, f"game connected: {self._connected_before_outage}"))
            return

        self._failures = 0
        if self._internet_up:
            return
        if self._stable_since is None:
            self._stable_since = now
        if now - self._stable_since >= self._s.stable_seconds:
            self._internet_up = True
            self._recovered_at = now
            self._pending = self._connected_before_outage
            lasted = int(now - (self._outage_start or now))
            out.append(Occurrence(Event.INTERNET_RESTORED, f"outage lasted about {lasted}s"))

    def _track_network_recovery(self, obs: Observation, out: list[Occurrence]) -> None:
        if not (self._pending and obs.game_running):
            return
        if obs.game_connected:
            if obs.now - self._recovered_at >= self._s.grace_seconds:
                self._pending = False
                out.append(Occurrence(Event.GAME_SURVIVED))
        else:
            self._pending = False
            out.append(Occurrence(Event.RECONNECT_NEEDED, reason=Reason.NETWORK))

    def _track_server_drop(self, obs: Observation, out: list[Occurrence]) -> None:
        now = obs.now
        online = self._internet_up and self._failures == 0 and not self._pending

        if online and self._was_connected and not obs.game_connected and obs.game_running and not self._watching:
            self._watching = True
            self._drop_at = now
            self._server_failures = 0
            self._server_down = False
            self._server_stable_since = None
            out.append(Occurrence(Event.DISCONNECTED_ONLINE, "internet is fine; checking whether the server is down"))

        if not self._watching:
            return
        if not online or not obs.game_running:
            self._watching = False
            return

        if obs.server_reachable is False:
            self._server_failures += 1
            self._server_stable_since = None
            if self._server_failures >= self._s.server_down_failures and not self._server_down:
                self._server_down = True
                out.append(Occurrence(Event.SERVER_DOWN, "the server stopped answering"))
        elif obs.server_reachable is True:
            self._server_failures = 0
            if self._server_down:
                if self._server_stable_since is None:
                    self._server_stable_since = now
                if now - self._server_stable_since >= self._s.stable_seconds:
                    self._watching = False
                    out.append(Occurrence(Event.SERVER_BACK, "the server is answering again"))
                    out.append(Occurrence(Event.RECONNECT_NEEDED, reason=Reason.SERVER))
                    return

        if not self._server_down and now - self._drop_at >= self._s.unknown_drop_seconds:
            self._watching = False
            if self._s.reconnect_on_unknown:
                out.append(Occurrence(Event.RECONNECT_NEEDED, "reconnect_on_unknown is on", Reason.UNKNOWN))
            else:
                out.append(Occurrence(
                    Event.DROP_NOT_ACTED,
                    "the server never stopped answering: a kick, ban or client error? not reconnecting"))
