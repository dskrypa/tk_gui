"""
Wrapper for normalizing input to initialize PIL images and handle common resizing / conversion / caching tasks.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from hashlib import sha256
from io import BytesIO
from math import floor, ceil
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from cachetools import LRUCache
from PIL.Image import Resampling, MIME, Image as PILImage, open as open_image
from PIL.ImageTk import PhotoImage
from PIL.JpegImagePlugin import RAWMODE

from tk_gui.caching import cached_property
from tk_gui.utils import get_user_temp_dir

if TYPE_CHECKING:
    from tk_gui.typing import XY, ImageType, PathLike, OptXYF

__all__ = ['ImageWrapper', 'SourceImage', 'ResizedImage']
log = logging.getLogger(__name__)

Box = tuple[float, float, float, float]


class ImageWrapper(ABC):
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
    def size(self) -> XY:
        if (image := self.pil_image) is None:
            return 0, 0
        return image.size

    @cached_property
    def aspect_ratio(self) -> float:
        width, height = self.size
        return width / height

    def _new_aspect_ratio_size(self, width: float, height: float) -> XY:
        """Copied logic from :meth:`PIL.Image.Image.thumbnail`"""
        x, y = floor(width), floor(height)
        if x / y >= self.aspect_ratio:
            x = self._new_aspect_ratio_width(y)
        else:
            y = self._new_aspect_ratio_height(x)
        return x, y

    def _new_aspect_ratio_width(self, y: int) -> int:
        aspect = self.aspect_ratio
        return _round_aspect(y * aspect, key=lambda n: abs(aspect - n / y))

    def _new_aspect_ratio_height(self, x: int) -> int:
        aspect = self.aspect_ratio
        return _round_aspect(x / aspect, key=lambda n: 0 if n == 0 else abs(aspect - x / n))

    def target_size(self, size: OptXYF, keep_ratio: bool = True) -> XY:
        dst_w, dst_h = size
        if dst_w is dst_h is None:
            return self.size
        elif None not in size:
            if keep_ratio:
                return self._new_aspect_ratio_size(dst_w, dst_h)
            return floor(dst_w), floor(dst_h)
        elif keep_ratio:
            if dst_w is None:
                dst_h = floor(dst_h)
                dst_w = self._new_aspect_ratio_width(dst_h)
            elif dst_h is None:
                dst_w = floor(dst_w)
                dst_h = self._new_aspect_ratio_height(dst_w)
            return dst_w, dst_h
        else:
            src_w, src_h = self.size
            if dst_w is None:
                return src_w, floor(dst_h)
            elif dst_h is None:
                return floor(dst_w), src_h

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

    def get_image_as_size(
        self,
        size: XY,
        keep_ratio: bool = True,
        resample: Resampling = None,
        box: Box = None,
        reducing_gap: float = None,
    ) -> PILImage:
        size = self.target_size(size, keep_ratio)
        image = self.pil_image
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
        if isinstance(image, ResizedImage):
            return image.source
        elif isinstance(image, SourceImage):
            return image
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
        **kwargs,
    ) -> ResizedImage:
        if not size or size == self.size:
            return ResizedImage(self, self.pil_image)

        if not use_cache:
            path = None
        elif path := resized_cache.get_cache_path(self, size, keep_ratio):
            try:
                return ResizedImage(self, resized_cache[path], path)
            except KeyError:  # It was not cached, but the path can be used to store it in the cache
                pass

        image = self.get_image_as_size(size, keep_ratio, resample=resample, **kwargs)
        resized_cache[path] = resized = ResizedImage(self, image, path)
        return resized


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
        return self.size[0] / self.source.size[1]

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

    def get_cache_path(self, source: SourceImage, size: XY, keep_ratio: bool = True) -> Path | None:
        src_w, src_h = source.size
        dst_w, dst_h = source.target_size(size, keep_ratio)
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


def _round_aspect(number: float, key: Callable[[float], float]) -> int:
    rounded = min(floor(number), ceil(number), key=key)
    return rounded if rounded > 1 else 1
