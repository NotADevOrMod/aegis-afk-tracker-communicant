"""
Everything that talks to Windows: finding the game window, the foreground check, reading screen pixels, and
sending mouse and keyboard input. Standard library only (ctypes).
"""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Optional

if sys.platform != "win32":  # pragma: no cover
    raise ImportError("aegis_reconnect.winapi only works on Windows")

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

VK_RETURN = 0x0D
VK_F8 = 0x77
INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x0002, 0x0004
SW_RESTORE = 9
MAPVK_VK_TO_VSC = 0


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _InputUnion(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _InputUnion)]


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsHungAppWindow.argtypes = [wintypes.HWND]
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
gdi32.GetPixel.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.GetPixel.restype = wintypes.DWORD
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        return self.left + self.width // 2, self.top + self.height // 2


def make_dpi_aware() -> None:
    """Call first. Without it Windows hands us scaled coordinates and clicks land in the wrong place."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor
    except (AttributeError, OSError):
        user32.SetProcessDPIAware()


# --- windows --------------------------------------------------------------------------------------

def find_window(pids: set[int], title_part: str) -> Optional[tuple[int, int]]:
    """(hwnd, pid) of the first visible window owned by one of `pids` whose title contains `title_part`."""
    found: list[tuple[int, int]] = []
    needle = title_part.lower()

    def callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids:
                length = user32.GetWindowTextLengthW(hwnd)
                if length:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buffer, length + 1)
                    if needle in buffer.value.lower():
                        found.append((hwnd, pid.value))
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return found[0] if found else None


def client_area(hwnd: int) -> Rect:
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    return Rect(origin.x, origin.y, rect.right - rect.left, rect.bottom - rect.top)


def is_hung(hwnd: int) -> bool:
    """True if Windows considers the window 'not responding'."""
    return bool(user32.IsHungAppWindow(hwnd))


def foreground_pid() -> int:
    window = user32.GetForegroundWindow()
    if not window:
        return -1
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
    return int(pid.value)


def bring_to_front(hwnd: int) -> None:
    """Windows refuses to let background programs steal focus; attaching to the current owner's input queue is the usual workaround."""
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    foreground = user32.GetForegroundWindow()
    this_thread = kernel32.GetCurrentThreadId()
    foreground_thread = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
    attached = False
    if foreground_thread and foreground_thread != this_thread:
        attached = bool(user32.AttachThreadInput(this_thread, foreground_thread, True))
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    if attached:
        user32.AttachThreadInput(this_thread, foreground_thread, False)


# --- pixels ---------------------------------------------------------------------------------------

class ScreenSampler:
    """Reads single screen pixels. Use as a context manager so the device context is released."""

    def __enter__(self) -> "ScreenSampler":
        self._dc = user32.GetDC(None)
        return self

    def __exit__(self, *exc) -> None:
        user32.ReleaseDC(None, self._dc)

    def pixel(self, x: int, y: int) -> tuple[int, int, int]:
        colour = gdi32.GetPixel(self._dc, x, y)
        if colour == 0xFFFFFFFF:  # CLR_INVALID: off-screen
            return (-999, -999, -999)
        return (colour & 0xFF, (colour >> 8) & 0xFF, (colour >> 16) & 0xFF)


# --- input ----------------------------------------------------------------------------------------

def _send(*inputs: INPUT) -> None:
    array = (INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), array, ctypes.sizeof(INPUT))


def _key(vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
    item = INPUT(type=INPUT_KEYBOARD)
    item.u.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    return item


def _mouse(flags: int) -> INPUT:
    item = INPUT(type=INPUT_MOUSE)
    item.u.mi = MOUSEINPUT(0, 0, 0, flags, 0, 0)
    return item


def cursor_pos() -> tuple[int, int]:
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def click(x: int, y: int) -> None:
    user32.SetCursorPos(x, y)
    time.sleep(0.2)  # let the game see the cursor arrive and highlight the button
    _send(_mouse(MOUSEEVENTF_LEFTDOWN))
    time.sleep(0.08)
    _send(_mouse(MOUSEEVENTF_LEFTUP))


def tap_key(vk: int) -> None:
    """A real key press with a scan code, which is what the game's key bindings listen for."""
    scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    _send(_key(vk, scan, 0))
    time.sleep(0.05)
    _send(_key(vk, scan, KEYEVENTF_KEYUP))


def type_text(text: str, delay: float = 0.04) -> None:
    """Types characters as text (not key presses), which is what a chat box expects."""
    for ch in text:
        code = ord(ch)
        if code > 0xFFFF:
            continue
        _send(_key(0, code, KEYEVENTF_UNICODE))
        time.sleep(delay / 2)
        _send(_key(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
        time.sleep(delay / 2)


def vk_for(name: str) -> int:
    """Virtual-key code for a single letter or digit, or '/'."""
    if len(name) == 1 and name.isalnum():
        return ord(name.upper())
    if name == "/":
        return 0xBF
    raise ValueError(f"Unsupported chat key {name!r}: use one letter or digit, or '/'")


def key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def idle_seconds() -> float:
    info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    now = kernel32.GetTickCount() & 0xFFFFFFFF
    return ((now - info.dwTime) & 0xFFFFFFFF) / 1000.0


def beep() -> None:
    import winsound
    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
