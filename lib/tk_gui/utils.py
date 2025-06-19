"""
Utils for the Tkinter GUI package.

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from getpass import getuser
from inspect import stack
from math import log as math_log
from pathlib import Path
from platform import system
from tempfile import gettempdir
from time import monotonic
from typing import TYPE_CHECKING, Any, Callable, Collection, Type, TypeVar, Iterable, Sequence, Mapping

from .constants import STYLE_CONFIG_KEYS

if TYPE_CHECKING:
    from .typing import HasParent, Bool

__all__ = [
    'ON_WINDOWS', 'ON_LINUX', 'ON_MAC', 'Inheritable', 'ProgramMetadata',
    'tcl_version', 'max_line_len', 'call_with_popped', 'extract_kwargs', 'get_user_temp_dir', 'readable_bytes',
    'mapping_repr', 'timer',
]
log = logging.getLogger(__name__)

_NotSet = object()
_OS = system().lower()
ON_WINDOWS = _OS == 'windows'
ON_LINUX = _OS == 'linux'
ON_MAC = _OS == 'darwin'

T = TypeVar('T')


class Inheritable:
    """An attribute whose value can be inherited from a parent"""

    __slots__ = ('parent_attr', 'default', 'type', 'name', 'attr_name')

    def __init__(
        self, parent_attr: str = None, default: Any = _NotSet, type: Callable = None, attr_name: str = 'parent'  # noqa
    ):
        """
        :param parent_attr: The attribute within the parent that holds the value to inherit, if different from the
          name of this attribute.
        :param default: The default value to return when no specific value is stored in the instance, instead of
          inheriting from the parent.
        :param type: A callable used to convert new values to the expected type when this attribute is set.
        :param attr_name: The name of the ``parent`` attribute in this class
        """
        self.parent_attr = parent_attr
        self.default = default
        self.type = type
        self.attr_name = attr_name

    def __set_name__(self, owner: Type[HasParent], name: str):
        self.name = name

    def __get__(self, instance: HasParent | None, owner: Type[HasParent]):
        if instance is None:
            return self
        try:
            return instance.__dict__[self.name]
        except KeyError:
            if (default := self.default) is not _NotSet:
                return default
            parent = getattr(instance, self.attr_name)
            return getattr(parent, self.parent_attr or self.name)

    def __set__(self, instance: HasParent, value):
        if value is not None:
            if type_func := self.type:
                value = type_func(value)
            instance.__dict__[self.name] = value


# region Metadata


class MetadataField:
    __slots__ = ('name',)

    def __set_name__(self, owner, name: str):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.globals.get(f'__{self.name}__', instance.default)


class ProgramMetadata:
    __slots__ = ('installed_via_setup', 'globals', 'path', 'name', 'default')

    author: str = MetadataField()
    version: str = MetadataField()
    url: str = MetadataField()
    author_email: str = MetadataField()

    def __init__(self, default: str = '[unknown]'):
        self.default = default
        self.installed_via_setup, self.globals, self.path = self._get_top_level()
        self.name = self._get_name()

    def _get_top_level(self) -> tuple[bool, dict[str, Any], Path]:
        try:
            return self._get_real_top_level()
        except Exception as e:  # noqa
            log.debug(f'Error determining top-level program info: {e}')
            try:
                path = Path(sys.argv[0])
            except IndexError:
                path = Path.cwd().joinpath('[unknown]')
            return False, {}, path

    # noinspection PyUnboundLocalVariable
    def _get_real_top_level(self):  # noqa
        _stack = stack()
        top_level_frame_info = _stack[-1]
        path = Path(top_level_frame_info.filename)
        g = top_level_frame_info.frame.f_globals
        if (installed_via_setup := 'load_entry_point' in g and 'main' not in g) or path.stem == 'runpy':
            for level in reversed(_stack[:-1]):
                g = level.frame.f_globals
                if any(k in g for k in ('__author_email__', '__version__', '__url__')):
                    return installed_via_setup, g, Path(level.filename)

        if path.stem == 'runpy':
            level = _stack[-3]
            return installed_via_setup, level.frame.f_globals, Path(level.filename)

        return installed_via_setup, g, path

    def _get_name(self) -> str:
        path = self.path
        if self.installed_via_setup and path.name.endswith('-script.py'):
            try:
                return Path(sys.argv[0]).stem
            except IndexError:
                return path.stem[:-7]
        return path.stem


def tcl_version():
    try:
        return tcl_version._tcl_version
    except AttributeError:
        from tkinter import Tcl

        tcl_version._tcl_version = ver = Tcl().eval('info patchlevel')
        return ver


# endregion


# region Misc Helpers


def max_line_len(lines: Collection[str]) -> int:
    if not lines:
        return 0
    return max(map(len, lines))


def call_with_popped(func: Callable, keys: Iterable[str], kwargs: dict[str, Any], args: Sequence[Any] = ()):
    if kwargs:
        func(*args, **{key: val for key in keys if (val := kwargs.pop(key, None)) is not None})
    else:
        func(*args)


def extract_style(
    kwargs: dict[str, T],
    _keys_intersection: Callable[[Iterable[str]], set[str] | frozenset[str]] = STYLE_CONFIG_KEYS.intersection,
) -> dict[str, T]:
    if kwargs:
        pop = kwargs.pop
        return {key: pop(key) for key in _keys_intersection(kwargs)}
    else:
        return {}


def extract_kwargs(kwargs: dict[str, T], keys: set[str] | frozenset[str]) -> dict[str, T]:
    if kwargs:
        pop = kwargs.pop
        return {key: pop(key) for key in keys.intersection(kwargs)}
    else:
        return {}


# endregion


def get_user_temp_dir(*sub_dirs, mode: int = 0o777) -> Path:
    """
    On Windows, returns `~/AppData/Local/Temp` or a sub-directory named after the current user of another temporary
    directory.  On Linux, returns a sub-directory named after the current user in `/tmp`, `/var/tmp`, or `/usr/tmp`.

    :param sub_dirs: Child directories of the chosen directory to include/create
    :param mode: Permissions to set if the directory needs to be created (0o777 by default, which matches the default
      for :meth:`pathlib.Path.mkdir`)
    """
    path = Path(gettempdir())
    if not ON_WINDOWS or not path.as_posix().endswith('AppData/Local/Temp'):
        path = path.joinpath(getuser())
    if sub_dirs:
        path = path.joinpath(*sub_dirs)
    if not path.exists():
        path.mkdir(mode=mode, parents=True, exist_ok=True)
    return path


def readable_bytes(
    size: float | int,
    dec_places: int = None,
    dec_by_unit: Mapping[str, int] = None,
    si: bool = False,
    bits: bool = False,
    i: bool = False,
    rate: bool | str = False,
) -> str:
    """
    :param size: The number of bytes to render as a human-readable string
    :param dec_places: Number of decimal places to include (overridden by dec_by_unit if specified)
    :param dec_by_unit: Mapping of {unit: number of decimal places to include}
    :param si: Use the International System of Units (SI) definition (base-10) instead of base-2 (default: base-2)
    :param bits: Use lower-case ``b`` instead of ``B``
    :param i: Include the ``i`` before ``B`` to indicate that this suffix is based on the base-2 value (this only
      affects the unit in the string - use ``si=True`` to use base-10)
    :param rate: Whether the unit is a rate or not.  If True, ``/s`` will be appended to the unit.  If a string is
      provided, that string will be appended instead.
    """
    units = ('B ', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')  # len=9 @ YB -> max exp = 8
    kilo = 1000 if si else 1024
    abs_size = abs(size)
    try:
        exp = min(int(math_log(abs_size, kilo)), 8) if abs_size > 0 else 0  # update 8 to len-1 if units are added
    except TypeError as e:
        raise ValueError(f'Invalid {size=}') from e

    unit = units[exp]
    if dec_places is not None:
        dec = dec_places
    elif dec_by_unit and isinstance(dec_by_unit, dict):
        dec = dec_by_unit.get(unit, 2)
    else:
        dec = 2 if exp else 0

    if bits:
        unit = unit.replace('B', 'b')
    if i and exp and not si:  # no `i` is necessary for B/b
        unit = unit[0] + 'i' + unit[1]
    if rate:
        unit = unit.strip() + ('/s' if rate is True else rate) + ('' if exp else ' ')  # noqa
    return f'{size / kilo ** exp:,.{dec}f} {unit}'


def mapping_repr(
    data: Mapping,
    keys: Collection[str] = None,
    sort: Bool = True,
    indent: int = 0,
    val_repr: Callable[[Any], str] = repr,
) -> str:
    if keys:
        kv_pairs = (kv for kv in data.items() if kv[0] in keys)
    else:
        kv_pairs = data.items()
    if sort:
        kv_pairs = sorted(kv_pairs)

    inner = ' ' * (indent + 4)
    outer = ' ' * indent
    return '{\n' + ',\n'.join(f'{inner}{k!r}: {val_repr(v)}' for k, v in kv_pairs) + f'\n{outer}}}'


@contextmanager
def timer(prefix: str, log_lvl: int = logging.DEBUG):
    start = monotonic()
    yield
    elapsed = monotonic() - start
    log.log(log_lvl, f'{prefix} in seconds={elapsed:,.3f}')
