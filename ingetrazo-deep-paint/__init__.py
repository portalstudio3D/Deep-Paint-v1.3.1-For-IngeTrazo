# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo Community Contributors.
"""
Deep Material Painter for IngeTrazo.
Allows painting faces and assigning materials directly to geometry inside
groups and components without having to open/edit each container.
"""
import sys
from pathlib import Path

_pkg_dir = str(Path(__file__).resolve().parent)
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

from .deep_paint import (
    DeepPaintTool,
    DeepPaintPanel,
    DeepPaintToolbar,
    ResetFaceMaterialCommand,
    setup,
    DISPLAY_NAME,
    VERSION,
)

__all__ = [
    "DeepPaintTool",
    "DeepPaintPanel",
    "DeepPaintToolbar",
    "ResetFaceMaterialCommand",
    "setup",
    "DISPLAY_NAME",
    "VERSION",
]
