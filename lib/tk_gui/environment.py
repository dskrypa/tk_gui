from __future__ import annotations

from os import environ
from platform import system

from .enums import DisplayServer

__all__ = ['ON_WINDOWS', 'ON_LINUX', 'ON_MAC', 'DISPLAY_SERVER']

_OS = system().lower()
ON_WINDOWS = _OS == 'windows'
ON_LINUX = _OS == 'linux'
ON_MAC = _OS == 'darwin'


def _detect_display_server() -> DisplayServer:
    if ON_LINUX:
        session_type = environ.get('XDG_SESSION_TYPE', '').lower()
        if session_type == 'x11':
            return DisplayServer.X11
        elif session_type == 'wayland':
            return DisplayServer.WAYLAND
        else:
            return DisplayServer.OTHER
    elif ON_WINDOWS:
        return DisplayServer.DWM
    elif ON_MAC:
        return DisplayServer.QUARTZ_COMPOSITOR
    else:
        return DisplayServer.OTHER


DISPLAY_SERVER: DisplayServer = _detect_display_server()
