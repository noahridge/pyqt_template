"""hmi — a robust, scalable PyQt6 HMI application template.

The console-script entry point ``hmi`` (and ``python -m hmi``) calls
:func:`main`, defined in :mod:`hmi.app`.
"""

from __future__ import annotations

import sys

__version__ = "0.1.0"


def main() -> None:
    """Entry point: build the app and run the Qt event loop."""
    from hmi.app import main as _main

    sys.exit(_main())
