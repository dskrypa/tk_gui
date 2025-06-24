"""
Wrapper for normalizing input to initialize PIL images and handle common resizing / conversion / caching tasks.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

import PIL.Image as ImageModule
from cachetools import LRUCache
from PIL.Image import Resampling, MIME, Image as PILImage, open as open_image, new as new_image
from PIL.ImageTk import PhotoImage
from PIL.JpegImagePlugin import RAWMODE

from tk_gui.caching import cached_property
from tk_gui.constants import IMAGE_MODE_TO_BPP
from tk_gui.enums import ImageResizeMode
from tk_gui.geometry import Box, Sized
from tk_gui.utils import get_user_temp_dir

if TYPE_CHECKING:
    from tk_gui.typing import XY, ImageType, PathLike, Color, ImgResizeMode
    from .icons import Icons, Icon

__all__ = ['ImageWrapper', 'SourceImage', 'ResizedImage', 'IconSourceImage']
log = logging.getLogger(__name__)


class ImageWrapper(Sized, ABC):
    @property
    @abstractmethod
    def pil_image(self) -> PILImage | None:
        raise NotImplementedError

    @property
    def name(self) -> str | None:
        return None

    @property
    @abstractmethod
    def source(self) -> SourceImage:
        raise NotImplementedError

    def __repr__(self) -> str:
        width, height = self.size
        ar_x, ar_y = self.aspect_ratio.as_integer_ratio()
        name, mode, mime = self.name, self.pil_image.mode, self.mime_type
        if (size_pct := self.size_percent) != 1:
            size_str = f'size={width}x{height} ({size_pct:.2%})'
        else:
            size_str = f'size={width}x{height}'
        return f'<{self.__class__.__name__}[{name!r}, {size_str}, ratio={ar_x}:{ar_y}, {mode=}, {mime=}]>'

    # region Size

    @cached_property(block=False)
    def width(self) -> int:
        return self.size[0]

    @cached_property(block=False)
    def height(self) -> int:
        return self.size[1]

    @cached_property(block=False)
    def size(self) -> XY:
        try:
            return self.pil_image.size
        except AttributeError:  # self.pil_image is likely None
            return 0, 0

    @cached_property(block=False)
    def size_percent(self) -> float:
        return (self.width_percent + self.height_percent) / 2

    @cached_property(block=False)
    def width_percent(self) -> float:
        return self.size[0] / self.source.size[0]

    @cached_property(block=False)
    def height_percent(self) -> float:
        return self.size[1] / self.source.size[1]

    # endregion

    def target_size(self, size: XY, keep_ratio: bool = True, resize_mode: ImgResizeMode = ImageResizeMode.NONE) -> XY:
        resize_mode = ImageResizeMode(resize_mode)
        if resize_mode == ImageResizeMode.FIT_INSIDE:
            return self.fit_inside_size(size, keep_ratio)
        elif resize_mode == ImageResizeMode.FILL:
            return self.fill_size(size, keep_ratio)
        else:
            return super().target_size(size, keep_ratio)

    @cached_property(block=False)
    def box(self) -> Box:
        return Box.from_pos_and_size(0, 0, *self.size)

    def get_bbox(self) -> Box:
        return Box(*self.pil_image.getbbox())

    # region Format

    @cached_property(block=False)
    def format(self) -> str:
        return self.pil_image.format or ('png' if self.pil_image.mode == 'RGBA' else 'jpeg')

    def as_format(self, format: str = None) -> PILImage:  # noqa
        return self._as_format(target_format=format)[0]

    def _as_format(self, path: PathLike = None, target_format: str = None) -> tuple[PILImage, str]:
        image = self.pil_image
        target_format = self._get_target_format(path, target_format)
        if target_format.lower() == 'jpeg' and image.mode not in RAWMODE:
            image = image.convert('RGB')
        return image, target_format

    def _get_target_format(self, path: PathLike = None, target_format: str = None) -> str:
        if target_format:
            return target_format
        elif not path:
            return self.format

        if not isinstance(path, Path):
            path = Path(path)
        if not ImageModule.EXTENSION:
            ImageModule.init()
        return ImageModule.EXTENSION.get(path.suffix.lower()) or self.format

    @cached_property(block=False)
    def mime_type(self) -> str | None:
        return MIME.get(self.format)

    # endregion

    @cached_property(block=False)
    def bits_per_pixel(self) -> int | None:
        return IMAGE_MODE_TO_BPP.get(self.pil_image.mode)

    @cached_property
    def raw_size(self) -> int:
        image = self.pil_image
        image.load()
        return len(image.im)  # noqa  # This provides the raw / uncompressed size

    def get_image_as_size(
        self,
        size: XY,
        keep_ratio: bool = True,
        resample: Resampling = None,
        box: tuple[float, float, float, float] = None,
        reducing_gap: float = None,
        resize_mode: ImgResizeMode = ImageResizeMode.NONE,
    ) -> PILImage:
        size = self.target_size(size, keep_ratio, resize_mode)
        if not (image := self.pil_image):
            return new_image('RGB', size)
        if image.mode == 'P' and resample not in (None, Resampling.NEAREST):
            # In this case, Image.resize ignores the resample arg and uses Resampling.NEAREST, so convert to RGB first
            image = image.convert('RGB')
        return image.resize(size, resample=resample, box=box, reducing_gap=reducing_gap)

    def save_as(self, path: PathLike, format: str = None):  # noqa
        image, target_format = self._as_format(path, format)
        with Path(path).expanduser().open('wb') as f:
            image.save(f, target_format)

    def to_bytes(self, format: str = None) -> bytes:  # noqa
        image, target_format = self._as_format(target_format=format)
        bio = BytesIO()
        image.save(bio, target_format)
        return bio.getvalue()

    def as_tk_image(self) -> PhotoImage:
        return PhotoImage(self.pil_image)


class SourceImage(ImageWrapper):
    source: SourceImage = None
    width_percent = height_percent = 1

    def __init__(self, image: ImageType):
        self._original = image
        self.source = self

    @classmethod
    def from_image(cls, image: ImageType | ImageWrapper) -> SourceImage:
        try:
            return image.source
        except AttributeError:
            return cls(image)

    @cached_property(block=False)
    def name(self) -> str | None:
        try:
            return self.path.name
        except AttributeError:
            return None

    @cached_property(block=False)
    def path(self) -> Path | None:
        image = self._original
        if isinstance(image, Path):
            return image
        elif isinstance(image, str):
            return Path(image).expanduser()
        elif path := getattr(image, 'filename', None) or getattr(getattr(image, 'fp', None), 'name', None):
            return Path(path)  # noqa
        return None

    @cached_property
    def pil_image(self) -> PILImage | None:
        match self._original:  # noqa
            case None | PILImage():
                return self._original
            case bytes():
                return open_image(BytesIO(self._original))
            case Path() | str():
                path = Path(self._original).expanduser()
                if not path.is_file():
                    raise ValueError(f'Invalid image path={path.as_posix()!r} - it is not a file')
                return open_image(path)
            case _:
                raise TypeError(
                    f'Image must be bytes, None, Path, str, or a PIL.Image.Image - found {type(self._original)}'
                )

    @cached_property
    def sha256sum(self) -> str | None:
        if (image := self._original) is None:
            return None
        elif isinstance(image, bytes):
            return sha256(image).hexdigest()
        elif isinstance(image, (Path, str)):
            return sha256(self.path.read_bytes()).hexdigest()
        else:
            return sha256(self.to_bytes()).hexdigest()

    def as_size(
        self,
        size: XY | None,
        keep_ratio: bool = True,
        resample: Resampling | None = Resampling.LANCZOS,
        use_cache: bool = False,
        resize_mode: ImgResizeMode = ImageResizeMode.NONE,
        **kwargs,
    ) -> ResizedImage:
        if not size or size == self.size:
            return ResizedImage(self, self.pil_image)

        if not use_cache:
            path = None
        elif path := resized_cache.get_cache_path(self, size, keep_ratio, resize_mode):
            try:
                return ResizedImage(self, resized_cache[path], path)
            except KeyError:  # It was not cached, but the path can be used to store it in the cache
                pass

        image = self.get_image_as_size(size, keep_ratio, resample=resample, resize_mode=resize_mode, **kwargs)
        resized_cache[path] = resized = ResizedImage(self, image, path)
        return resized

    def save_as_with_prompt(self, event=None, init_dir: PathLike = None):
        from tk_gui.popups.paths import SaveAs

        # file_types = [
        #     ('ALL Types', '*.*'),
        #     ('BMP - Windows Bitmap', '*.bmp'),
        #     ('JPG - JPG/JPEG Format', '*.jpg *.jpeg'),
        #     ('PNG - Portable Network Graphics', '*.png'),
        # ]
        # kwargs: dict[str, Any] = {'file_types': file_types}
        if path := self.path:
            kwargs = {'initial_name': path.name, 'default_ext': path.suffix}
        else:
            kwargs = {'default_ext': '.png' if self.pil_image.mode == 'RGBA' else '.jpg'}

        if path := SaveAs(init_dir, **kwargs).run():
            log.info(f'Saving {self} as {path}')
            self.save_as(path)

    def as_popup_src_img(self) -> SourceImage:
        return self


class IconSourceImage(SourceImage):
    def __init__(
        self,
        icons: Icons,
        icon: Icon,
        image: PILImage = None,
        color: Color = '#000000',
        bg: Color = '#ffffff',
        popup_size: int = 500,
    ):
        self._icons = icons
        self._icon = icon
        self._color = color
        self._bg = bg
        self._popup_size = popup_size
        if image is None:
            size = int(icons.font.size)
            image = icons.draw(icon, (size, size), color=color, bg=bg)
        super().__init__(image)

    def as_size(self, size: XY | None, keep_ratio: bool = True, **kwargs) -> IconSourceImage | ResizedImage:
        if not size or size == self.size:
            return self
        return ResizedImage(
            self, self._icons.draw(self._icon, self.target_size(size, keep_ratio), color=self._color, bg=self._bg)
        )

    def as_popup_src_img(self) -> IconSourceImage:
        if (popup_size := self._popup_size) == self.pil_image.size[0]:
            return self
        image = self._icons.draw(self._icon, (popup_size, popup_size), color=self._color, bg=self._bg)
        return self.__class__(self._icons, self._icon, image, color=self._color, bg=self._bg, popup_size=popup_size)


class ResizedImage(ImageWrapper):
    source: SourceImage = None
    pil_image: PILImage = None  # Satisfies the abstract property so it can be stored in init

    def __init__(self, source: SourceImage, image: PILImage, cache_path: Path | None = None):
        self.source = source
        self.pil_image = image
        self.cache_path = cache_path

    @cached_property(block=False)
    def name(self) -> str | None:
        return self.source.name


class ImageCache:
    max_cache_size: XY

    def __init__(self, mem_size: int = 20, max_cache_size: XY = (500, 500)):
        self._cache = LRUCache(mem_size)
        self.max_cache_size = max_cache_size

    @cached_property(block=False)
    def cache_dir(self) -> Path:
        return get_user_temp_dir('tk_gui_image_cache')

    def get_cache_path(
        self, source: SourceImage, size: XY, keep_ratio: bool = True, resize_mode: ImgResizeMode = ImageResizeMode.NONE
    ) -> Path | None:
        src_w, src_h = source.size
        dst_w, dst_h = source.target_size(size, keep_ratio, resize_mode)
        max_w, max_h = self.max_cache_size
        if (
            not (src_hash := source.sha256sum)      # Image is None
            or (dst_w > max_w or dst_h > max_h)     # Too large to save
            or (src_w < dst_w or src_h < dst_h)     # Smaller than target size
            or (src_w == dst_w and src_h == dst_h)  # Already at the target size
        ):
            return None

        return self.cache_dir.joinpath(f'{src_hash}_{src_w}x{src_h}_{dst_w}x{dst_h}.thumb')

    def load(self, path: Path) -> PILImage:
        try:
            return self._cache[path]
        except KeyError:
            pass
        self._cache[path] = image = open_image(path)
        log.log(9, f'Loaded thumbnail from {path.as_posix()}')
        return image

    def __getitem__(self, path: Path) -> PILImage:
        try:
            return self.load(path)
        except FileNotFoundError:
            pass
        except OSError as e:
            log.debug(f'Error loading cached image from path={path.as_posix()!r}: {e}')
        raise KeyError(path)

    def __setitem__(self, path: Path | None, image: ImageWrapper):
        if not path:
            return
        try:
            image.save_as(path)
        except OSError as e:
            log.debug(f'Error saving image to cache path={path.as_posix()!r}: {e}')
        else:
            log.debug(f'Saved image to cache: {path.as_posix()}')


resized_cache: ImageCache = ImageCache()
