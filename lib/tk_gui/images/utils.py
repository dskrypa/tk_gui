"""
Utilities for working with PIL images.

:author: Doug Skrypa
"""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from importlib.resources import path as get_data_path
from math import floor, ceil
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Union

from PIL.Image import Image as PILImage, open as open_image
from PIL.JpegImagePlugin import RAWMODE

if TYPE_CHECKING:
    from ..typing import XY, ImageType

__all__ = [
    'as_image', 'image_path', 'image_to_bytes', 'scale_image', 'calculate_resize', 'prepare_dir', 'get_image_and_hash'
]


with get_data_path('tk_gui', 'icons') as _icon_path:
    ICONS_DIR = _icon_path


def image_path(rel_path: str) -> Path:
    return ICONS_DIR.joinpath(rel_path)


def prepare_dir(path: Union[Path, str]) -> Path:
    path = Path(path).expanduser().resolve() if isinstance(path, str) else path
    if path.exists():
        if not path.is_dir():
            raise ValueError(f'Invalid path={path.as_posix()!r} - it must be a directory')
    else:
        path.mkdir(parents=True, exist_ok=True)
    return path


def as_image(image: ImageType) -> PILImage:
    if image is None or isinstance(image, PILImage):
        return image
    elif isinstance(image, bytes):
        return open_image(BytesIO(image))
    elif isinstance(image, (Path, str)):
        path = Path(image).expanduser()
        if not path.is_file():
            raise ValueError(f'Invalid image path={path.as_posix()!r} - it is not a file')
        return open_image(path)
    else:
        raise TypeError(f'Image must be bytes, None, Path, str, or a PIL.Image.Image - found {type(image)}')


def get_image_and_hash(image: ImageType) -> tuple[PILImage | None, str | None]:
    if image is None:
        return None, None
    elif isinstance(image, bytes):
        return open_image(BytesIO(image)), sha256(image).hexdigest()
    elif isinstance(image, (Path, str)):
        path = Path(image).expanduser()
        if not path.is_file():
            raise ValueError(f'Invalid image path={path.as_posix()!r} - it is not a file')

        return open_image(path), sha256(path.read_bytes()).hexdigest()
    elif isinstance(image, PILImage):
        return image, sha256(_image_to_bytes(image)).hexdigest()
    else:
        raise TypeError(f'Image must be bytes, None, Path, str, or a PIL.Image.Image - found {type(image)}')


def image_to_bytes(image: ImageType, format: str = None, size: XY = None, **kwargs) -> bytes:  # noqa
    image = as_image(image)
    if size:
        image = scale_image(image, *size, **kwargs)
    return _image_to_bytes(image, format)


def _image_to_bytes(image: PILImage, img_format: str = None) -> bytes:
    if not img_format:
        img_format = image.format or ('png' if image.mode == 'RGBA' else 'jpeg')
    if img_format == 'jpeg' and image.mode not in RAWMODE:
        image = image.convert('RGB')

    bio = BytesIO()
    image.save(bio, img_format)
    return bio.getvalue()


# region Image Resizing


def scale_image(image: PILImage, width: float, height: float, **kwargs) -> PILImage:
    new_size = calculate_resize(*image.size, width, height)
    return image.resize(new_size, **kwargs)


def calculate_resize(src_w: float, src_h: float, new_w: float, new_h: float) -> XY:
    """Copied logic from :meth:`PIL.Image.Image.thumbnail`"""
    x, y = floor(new_w), floor(new_h)
    aspect = src_w / src_h
    if x / y >= aspect:
        x = _round_aspect(y * aspect, key=lambda n: abs(aspect - n / y))
    else:
        y = _round_aspect(x / aspect, key=lambda n: 0 if n == 0 else abs(aspect - x / n))
    return x, y


def _round_aspect(number: float, key: Callable[[float], float]) -> int:
    rounded = min(floor(number), ceil(number), key=key)
    return rounded if rounded > 1 else 1


# endregion
