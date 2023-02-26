"""
Popups that allow users to choose an item from a list of options.
"""

from __future__ import annotations

import logging
from textwrap import wrap
from typing import TYPE_CHECKING, TypeVar, Generic, Collection, Mapping, Callable, Any, Type

from ..elements import Button, RadioGroup, Radio, ScrollFrame, Image
from ..images.icons import placeholder_icon_cache
from .base import BasicPopup

if TYPE_CHECKING:
    from ..typing import XY, ImageType, Layout

__all__ = ['ChoiceMapPopup', 'ChooseItemPopup', 'ChooseImagePopup', 'choose_item']
log = logging.getLogger(__name__)

K = TypeVar('K')
V = TypeVar('V')
P = TypeVar('P', bound='ChoiceMapPopup')
ReprFunc = Callable[[Any], str]


class ChoiceMapPopup(Generic[K, V], BasicPopup):
    def __init__(self, items: Mapping[K, V], **kwargs):
        super().__init__(bind_esc=True, **kwargs)
        self.items = items

    @classmethod
    def with_auto_prompt(
        cls: Type[P],
        items: Mapping[K, V],
        *,
        item_name: str = 'value',
        source: Any = '',
        text: str = None,
        title: str = None,
        **kwargs,
    ) -> P[K, V]:
        if not title:
            title = f'Select {a_or_an(item_name)} {item_name}'
        if not text:
            text = f'Found multiple {item_name}s{_prepare_source(source)} - which {item_name} should be used?'
        return cls(items, title=title, text=text, **kwargs)

    def prepare_choices(self) -> Layout:
        yield from ([Radio(key, val)] for key, val in self.items.items())

    def get_frame_size(self) -> XY | None:
        return None

    def get_pre_window_layout(self):
        yield from self.prepare_text()
        submit_button = Button('Submit', disabled=True, bind_enter=True)
        with RadioGroup('item_choices', change_cb=lambda *a: submit_button.enable(), include_label=True):
            yield [ScrollFrame(self.prepare_choices(), scroll_y=True, expand=True, size=self.get_frame_size())]
        yield [submit_button]

    def get_results(self) -> tuple[K, V] | None:
        results = super().get_results()
        return results.get('item_choices')


class ChooseItemPopup(ChoiceMapPopup[K, V]):
    def __init__(self, items: Mapping[K, V] | Collection[V], *, repr_func: ReprFunc = repr, **kwargs):
        if not isinstance(items, Mapping):
            items = {repr_func(i): i for i in items}
        super().__init__(items, **kwargs)

    @classmethod
    def with_auto_prompt(
        cls,
        items: Mapping[K, V] | Collection[V],
        *,
        repr_func: ReprFunc = repr,
        **kwargs,
    ) -> ChooseItemPopup[K, V]:
        items = {repr_func(i): i for i in items}
        return super().with_auto_prompt(items, **kwargs)


class ChooseImagePopup(ChoiceMapPopup[K, 'ImageType']):
    def __init__(
        self,
        items: Mapping[K, ImageType],
        *,
        img_size: XY = (250, 250),
        img_title_fmt: str = None,
        **kwargs,
    ):
        super().__init__(items, **kwargs)
        self.img_size = img_size
        self.img_title_fmt = img_title_fmt

    @classmethod
    def with_auto_prompt(cls, items: Mapping[K, ImageType], *, item_name: str = 'image', **kwargs) -> ChooseImagePopup:
        return super().with_auto_prompt(items, item_name=item_name, **kwargs)

    def _prepare_image(self, title: K, image: ImageType) -> Image:
        if img_title_fmt := self.img_title_fmt:
            popup_title = img_title_fmt.format(title=title)
        else:
            popup_title = None
        return Image(image, size=self.img_size, popup=True, popup_title=popup_title)

    def get_frame_size(self) -> XY | None:
        monitor_height = self.get_monitor().height
        img_width, img_height = self.img_size
        per_img_height = (img_height + 20)
        images_shown = max(1, min(monitor_height // per_img_height, len(self.items)))
        max_frame_height = (monitor_height - 130) - 150  # max Window height: - 130
        if (frame_height := images_shown * per_img_height) > max_frame_height:
            frame_height = max_frame_height
        return (img_width + 300, frame_height)

    def prepare_choices(self) -> Layout:
        items = [
            ('\n'.join(wrap(title, break_long_words=False, break_on_hyphens=False, tabsize=4, width=30)), title, img)
            for title, img in self.items.items()
        ]
        label_width = max(len(line) for label, _, _ in items for line in label.splitlines())
        for label, title, orig_image in items:
            try:
                image = self._prepare_image(title, orig_image)
            except Exception:  # noqa
                log.error(f'Unable to render image={title!r}:', exc_info=True)
                image = Image(placeholder_icon_cache.get_placeholder(self.img_size), size=self.img_size)

            height = label.count('\n') + 1
            yield [Radio(label, title, size=(label_width, height)), image]

    def get_results(self) -> tuple[K, V] | None:
        try:
            label, title = super().get_results()
        except TypeError:
            return None
        else:
            return title, self.items[title]


def a_or_an(noun: str) -> str:
    if not noun:
        return 'a'
    return 'an' if noun[0] in 'aeiou' else 'a'


def _prepare_source(source: Any) -> str:
    if source:
        if not isinstance(source, str):
            source = str(source)
        if not source.startswith(' '):
            source = ' ' + source
        if not source.startswith((' for ', ' from ', ' in ')):
            source = ' for' + source
    return source


def choose_item(
    items: Mapping[K, V] | Collection[V],
    item_name: str = 'value',
    source: Any = '',
    *,
    text: str = None,
    title: str = None,
    repr_func: ReprFunc = repr,
    **kwargs,
) -> V | None:
    """
    Given a list of items from which only one value can be used, prompt the user to choose an item.  If only one item
    exists in the provided sequence, then that item is returned with no prompt.

    :param items: A collection of items to choose from.  If a dict/mapping is provided, then the value for the selected
      key will be returned.  If a non-dict/mapping is provided, then all values should have unique reprs.
    :param item_name: The name of the item to use in messages/prompts
    :param source: Where the items came from
    :param text: A message to be displayed before listing the items to choose from (default: automatically generated
      using the provided item_name and source)
    :param title: The title for the popup window
    :param repr_func: The function to use to generate a string representation of each item
    :return: The selected item
    """
    if not items:
        raise ValueError(f'No {item_name}s found{_prepare_source(source)}')
    elif len(items) == 1:
        try:
            return next(iter(items.values()))
        except AttributeError:
            return next(iter(items))
    else:
        popup = ChooseItemPopup.with_auto_prompt(
            items, item_name=item_name, source=source, text=text, title=title, repr_func=repr_func, **kwargs
        )
        try:
            return popup.run()[1]
        except TypeError:
            return None
