"""
ViewSpec contains the class and arguments necessary to initialize a View.
"""

from __future__ import annotations

from inspect import Signature
from typing import TYPE_CHECKING, TypeVar, ParamSpec, Callable, Iterator

if TYPE_CHECKING:
    from .view import View  # noqa

__all__ = ['ViewSpec']

V = TypeVar('V', bound='View')
P = ParamSpec('P', bound='View')
ViewType = Callable[P, V]


class ViewSpec:
    __slots__ = ('view_cls', 'args', 'kwargs', '_sig')
    view_cls: ViewType
    args: P.args
    kwargs: P.kwargs
    _sig: Signature

    def __init__(self, view_cls: ViewType, args: P.args, kwargs: P.kwargs):
        self.view_cls = view_cls
        self.args = args
        self.kwargs = kwargs

    def __iter__(self) -> Iterator[ViewType | P.args | P.kwargs]:
        yield self.view_cls
        yield self.args
        yield self.kwargs

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}({self.view_cls.__name__}, {self.args!r}, {self.kwargs!r})>'

    def __getitem__(self, key):
        try:
            return self.kwargs[key]
        except KeyError:
            pass
        sig = self.signature
        if key not in sig.parameters:
            raise KeyError(key)
        bound = sig.bind(self.args, self.kwargs)
        bound.apply_defaults()
        return bound.arguments[key]

    def __setitem__(self, key, value):
        self.kwargs[key] = value

    @property
    def signature(self) -> Signature:
        try:
            return self._sig
        except AttributeError:
            pass
        self._sig = sig = Signature.from_callable(self.view_cls)
        return sig

    @property
    def name(self) -> str:
        return self.view_cls.__name__
