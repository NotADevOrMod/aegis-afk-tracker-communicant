"""Finding the game, its server connection and its crash evidence."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import psutil

from . import winapi
from .config import Config
from .crash import CrashFile


@dataclass(frozen=True)
class GameWindow:
    pid: int
    hwnd: int


def find_game(cfg: Config) -> Optional[GameWindow]:
    """The game's main window, identified by process name AND window title (so a browser tab titled
    'Minecraft' is never mistaken for it)."""
    names = {n.lower().removesuffix(".exe") for n in cfg.process_names}
    pids = {
        p.pid for p in psutil.process_iter(["name"])
        if (p.info.get("name") or "").lower().removesuffix(".exe") in names
    }
    if not pids:
        return None
    found = winapi.find_window(pids, cfg.window_title)
    return GameWindow(pid=found[1], hwnd=found[0]) if found else None


def remote_server(pid: int, port: int) -> Optional[tuple[str, int]]:
    """(address, port) of the game's established connection to the server, or None if it has none."""
    try:
        process = psutil.Process(pid)
        list_connections = getattr(process, "net_connections", None) or process.connections
        for conn in list_connections(kind="tcp"):
            if conn.status != psutil.CONN_ESTABLISHED or not conn.raddr:
                continue
            if port > 0:
                if conn.raddr.port == port:
                    return conn.raddr.ip, conn.raddr.port
            elif conn.raddr.port not in (80, 443):
                return conn.raddr.ip, conn.raddr.port
    except psutil.NoSuchProcess:
        return None
    return None


def server_reachable(address: tuple[str, int], timeout: float = 2.0) -> bool:
    """True if something accepts a TCP connection at the server's address."""
    try:
        with socket.create_connection(address, timeout=timeout):
            return True
    except OSError:
        return False


def internet_ok(targets: list[list], timeout: float = 1.5) -> bool:
    """True if any target accepts a TCP connection."""
    for host, port in targets:
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def game_dirs(pid: int) -> list[Path]:
    """Folders where this game would leave a crash report: its --gameDir and its working directory."""
    found: list[Path] = []
    try:
        process = psutil.Process(pid)
        command = process.cmdline()
        for i, arg in enumerate(command):
            if arg == "--gameDir" and i + 1 < len(command):
                found.append(Path(command[i + 1]))
        found.append(Path(process.cwd()))
    except (psutil.Error, OSError):
        pass
    unique: list[Path] = []
    for folder in found:
        if folder.is_dir() and folder not in unique:
            unique.append(folder)
    return unique


def collect_crash_files(folders: list[Path]) -> list[CrashFile]:
    """Crash reports and JVM crash logs in the given folders, with their modification times."""
    files: list[CrashFile] = []
    for folder in folders:
        candidates = list((folder / "crash-reports").glob("crash-*.txt")) + list(folder.glob("hs_err_pid*.log"))
        for path in candidates:
            try:
                files.append(CrashFile(path.name, path.stat().st_mtime))
            except OSError:
                continue
    return files
