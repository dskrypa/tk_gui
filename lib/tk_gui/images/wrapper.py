"""
Wrapper for normalizing input to initialize PIL images and handle common resizing / conversion / caching tasks.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

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

    @cached_property
    def width(self) -> int:
        return self.size[0]

    @cached_property
    def height(self) -> int:
        return self.size[1]

    @cached_property
    def size(self) -> XY:
        if (image := self.pil_image) is None:
            return 0, 0
        return image.size

    @cached_property
    def size_percent(self) -> float:
        return (self.width_percent + self.height_percent) / 2

    @property
    @abstractmethod
    def width_percent(self) -> float:
        raise NotImplementedError

    @property
    @abstractmethod
    def height_percent(self) -> float:
        raise NotImplementedError

    # endregion

    def target_size(self, size: XY, keep_ratio: bool = True, resize_mode: ImgResizeMode = ImageResizeMode.NONE) -> XY:
        resize_mode = ImageResizeMode(resize_mode)
        if resize_mode == ImageResizeMode.FIT_INSIDE:
            return self.fit_inside_size(size, keep_ratio)
        elif resize_mode == ImageResizeMode.FILL:
            return self.fill_size(size, keep_ratio)
        else:
            return super().target_size(size, keep_ratio)

    @cached_property
    def box(self) -> Box:
        return Box.from_pos_and_size(0, 0, *self.size)

    def get_bbox(self) -> Box:
        return Box(*self.pil_image.getbbox())

    # region Format

    @cached_property
    def format(self) -> str:
        image = self.pil_image
        return image.format or ('png' if image.mode == 'RGBA' else 'jpeg')

    def as_format(self, format: str = None) -> PILImage:  # noqa
        return self._as_format(format)[0]

    def _as_format(self, target_format: str = None) -> tuple[PILImage, str]:
        image = self.pil_image
        if not target_format:
            target_format = self.format
        if target_format == 'jpeg' and image.mode not in RAWMODE:
            image = image.convert('RGB')
        return image, target_format

    @cached_property
    def mime_type(self) -> str | None:
        return MIME.get(self.format)

    # endregion

    @cached_property
    def bits_per_pixel(self) -> int | None:
        return IMAGE_MODE_TO_BPP.get(self.pil_image.mode)

    @cached_property
    def raw_size(self) -> int:
        image = self.pil_image
        image.load()
        return len(image.im)  # This provides the raw / uncompressed size

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
        image, target_format = self._as_format(format)
        with Path(path).expanduser().open('wb') as f:
            image.save(f, target_format)

    def to_bytes(self, format: str = None) -> bytes:  # noqa
        image, target_format = self._as_format(format)
        bio = BytesIO()
        image.save(bio, target_format)
        return bio.getvalue()

    def as_tk_image(self) -> PhotoImage:
        return PhotoImage(self.pil_image)


class SourceImage(ImageWrapper):
    width_percent = height_percent = 1

    def __init__(self, image: ImageType):
        self._original = image

    @classmethod
    def from_image(cls, image: ImageType | ImageWrapper) -> SourceImage:
        if isinstance(image, SourceImage):
            return image
        elif isinstance(image, ResizedImage):
            return image.source
        else:
            return cls(image)

    @cached_property
    def name(self) -> str | None:
        try:
            return self.path.name
        except AttributeError:
            return None

    @cached_property
    def path(self) -> Path | None:
        image = self._original
        if isinstance(image, Path):
            return image
        elif isinstance(image, str):
            return Path(image).expanduser()
        elif path := getattr(image, 'filename', None) or getattr(getattr(image, 'fp', None), 'name', None):
            return Path(path)
        return None

    @cached_property
    def pil_image(self) -> PILImage | None:
        image = self._original
        if image is None or isinstance(image, PILImage):
            return image
        elif isinstance(image, bytes):
            return open_image(BytesIO(image))
        elif isinstance(image, (Path, str)):
            path = Path(image).expanduser()
            if not path.is_file():
                raise ValueError(f'Invalid image path={path.as_posix()!r} - it is not a file')
            return open_image(path)
        raise TypeError(f'Image must be bytes, None, Path, str, or a PIL.Image.Image - found {type(image)}')

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
        from tk_gui.popups.raw import SaveAs

        file_types = [
            ('ALL Types', '*.*'),
            ('BMP - Windows Bitmap', '*.bmp'),
            ('JPG - JPG/JPEG Format', '*.jpg *.jpeg'),
            ('PNG - Portable Network Graphics', '*.png'),
        ]
        kwargs = {'file_types': file_types}
        if path := self.path:
            kwargs['initial_name'] = path.name
            kwargs['default_ext'] = path.suffix
        else:
            kwargs['default_ext'] = '.png' if self.pil_image.mode == 'RGBA' else '.jpg'

        if path := SaveAs(init_dir, **kwargs).run():
            # TODO: The `format` param needs to be explicitly provided to convert files, it seems
            log.info(f'Saving {self} as {path}')
            self.save_as(path)


class IconSourceImage(SourceImage):
    def __init__(
        self,
        icons: Icons,
        icon: Icon,
        image: PILImage = None,
        color: Color = '#000000',
        bg: Color = '#ffffff',
        init_size: int = 500,
    ):
        self._icons = icons
        self._icon = icon
        self._color = color
        self._bg = bg
        self._init_size = init_size
        if image is None:
            if (size := icons.font.size) < init_size:
                size = init_size
            image = icons.draw(icon, (size, size), color=color, bg=bg)
        super().__init__(image)

    @cached_property
    def size(self) -> XY:
        if (image := self.pil_image) is None or image.size[0] < self._init_size:
            size = (self._init_size, self._init_size)
            self._original = image = self._icons.draw(self._icon, size, color=self._color, bg=self._bg)
            self.__dict__['pil_image'] = image
        return image.size

    def as_size(self, size: XY | None, keep_ratio: bool = True, **kwargs) -> ResizedImage:
        if size:
            size = self.target_size(size, keep_ratio)
        if not size or size == self.size:
            return ResizedImage(self, self.pil_image)
        image = self._icons.draw(self._icon, size, color=self._color, bg=self._bg)
        return ResizedImage(self, image)


class ResizedImage(ImageWrapper):
    pil_image: PILImage = None  # Satisfies the abstract property so it can be stored in init

    def __init__(self, source: SourceImage, image: PILImage, cache_path: Path | None = None):
        self.source = source
        self.pil_image = image
        self.cache_path = cache_path

    @cached_property
    def name(self) -> str | None:
        return self.source.name

    @cached_property
    def width_percent(self) -> float:
        return self.size[0] / self.source.size[0]

    @cached_property
    def height_percent(self) -> float:
        return self.size[1] / self.source.size[1]


class ImageCache:
    max_cache_size: XY

    def __init__(self, mem_size: int = 20, max_cache_size: XY = (500, 500)):
        self._cache = LRUCache(mem_size)
        self.max_cache_size = max_cache_size

    @cached_property
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
