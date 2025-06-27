"""
Utils for the Tkinter GUI package.

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from getpass import getuser
from inspect import stack
from math import log as math_log
from pathlib import Path
from tempfile import gettempdir
from time import monotonic
from typing import TYPE_CHECKING, Any, Callable, Collection, Type, TypeVar, Iterable, Sequence, Mapping

from cli_command_parser.core import get_top_level_commands
from cli_command_parser.metadata import DistributionFinder

from .caching import cached_property
from .constants import STYLE_CONFIG_KEYS
from .environment import ON_WINDOWS

if TYPE_CHECKING:
    from importlib.metadata import Distribution

    from .typing import HasParent, Bool

__all__ = [
    'Inheritable', 'ProgramMetadata',
    'tcl_version', 'max_line_len', 'call_with_popped', 'extract_kwargs', 'get_user_temp_dir', 'readable_bytes',
    'mapping_repr', 'timer',
]
log = logging.getLogger(__name__)

_NotSet = object()

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


class ProgramMetadata:
    def __init__(self, default: str = '[unknown]'):
        self._dist_finder = DistributionFinder()
        self.default = default

    @cached_property
    def entry_point_path(self) -> Path:
        return Path(stack()[-1].filename)

    @cached_property
    def name(self) -> str:
        return self.entry_point_path.name

    @cached_property
    def _distribution(self) -> Distribution | None:
        if self.entry_point_path.parent.joinpath('activate').exists():
            # It's likely a generated entry point in a venv's bin/Scripts directory
            # On Linux, uv and pip both include `import sys` and `from pkg.mod import func`; pip also imports `re`
            import_pat = re.compile(r'^from (\S+) import .*')
            for line in self.entry_point_path.read_text('utf-8').splitlines():
                if m := import_pat.match(line):
                    return self._dist_finder.dist_for_pkg(m.group(1).split('.', 1)[0])

        if commands := get_top_level_commands():
            for command in commands:
                if dist := self._dist_finder.dist_for_obj(command):
                    return dist

        return None

    @cached_property
    def version(self) -> str:
        return self._distribution.version if self._distribution else self.default

    @cached_property
    def _author_email(self) -> tuple[str | None, str | None]:
        try:
            author_and_email = self._distribution.metadata['Author-email']
        except (KeyError, AttributeError, TypeError):
            return None, None
        if m := re.match(r'^(.+)\s+<(.+)>$', author_and_email):
            author, email = m.groups()
            return author, email
        elif '@' in author_and_email:
            return None, author_and_email
        else:
            return author_and_email, None

    @cached_property
    def author(self) -> str:
        try:
            author = self._distribution.metadata['Author']
        except (KeyError, AttributeError, TypeError):
            return self._author_email[0] or self.default
        else:
            # Until the `Implicit None on return values is deprecated and will raise KeyErrors.` behavior is removed,
            # the case where the value is None needs to be handled
            return author or self._author_email[0] or self.default

    @cached_property
    def email(self) -> str:
        return self._author_email[1] or self.default

    @cached_property
    def url(self) -> str:
        if self._distribution and (urls := self._dist_finder.get_urls(self._distribution)):
            for key in ('Source', 'Source Code', 'Home-page'):
                if url := urls.get(key):
                    return url
        return self.default


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
def timer(prefix: str, log_lvl: int = logging.DEBUG, hide_below: float | None = None):
    start = monotonic()
    yield
    elapsed = monotonic() - start
    if not hide_below or hide_below < elapsed:
        log.log(log_lvl, f'{prefix} in seconds={elapsed:,.3f}')
