from __future__ import annotations

from typing import Final

from foundation.version import PACKAGE_VERSION, PRODUCT_EDITION

__all__: Final[list[str]] = [
    "__description__",
    "__product_edition__",
    "__title__",
    "__version__",
]

__title__: Final[str] = "SH-3 DevKit"
__version__: Final[str] = PACKAGE_VERSION
__product_edition__: Final[str] = PRODUCT_EDITION
__description__: Final[str] = "SH-3 AI Operating System Development Toolkit"
