"""
Built-in driver discovery for peripheral devices.

Scans this package's submodules for PeripheralDevice subclasses and also
checks for externally installed drivers via entry points.
"""

import importlib
import importlib.metadata
import pkgutil
from typing import Type

from openperiph.base import PeripheralDevice


def _discover_builtin() -> dict[str, Type[PeripheralDevice]]:
    """Find all PeripheralDevice subclasses in this drivers package."""
    drivers: dict[str, Type[PeripheralDevice]] = {}
    for finder, name, _ispkg in pkgutil.iter_modules(__path__):
        mod = importlib.import_module(f'{__name__}.{name}')
        for attr in dir(mod):
            obj = getattr(mod, attr)
            # `obj.__module__ == mod.__name__` skips classes the module merely
            # imported rather than defined -- a thin driver like xlite_wired.py
            # imports its protocol parent (PulsarX2A) into its namespace, and
            # without this check whichever of the two sorts last in dir() would
            # win and silently register under the wrong module name.
            if (isinstance(obj, type) and issubclass(obj, PeripheralDevice)
                    and obj is not PeripheralDevice
                    and obj.__module__ == mod.__name__):
                drivers[name] = obj
    return drivers


def _discover_entrypoints() -> dict[str, Type[PeripheralDevice]]:
    """Find externally installed drivers via entry points."""
    drivers: dict[str, Type[PeripheralDevice]] = {}
    try:
        eps = importlib.metadata.entry_points(group='openperiph.drivers')
    except TypeError:
        # Python < 3.12 compat
        eps = importlib.metadata.entry_points().get('openperiph.drivers', [])
    for ep in eps:
        try:
            cls = ep.load()
            if isinstance(cls, type) and issubclass(cls, PeripheralDevice):
                drivers[ep.name] = cls
        except Exception:
            pass
    return drivers


def discover_all() -> dict[str, Type[PeripheralDevice]]:
    """Return all known drivers (built-in + entry points), keyed by name."""
    drivers = _discover_builtin()
    drivers.update(_discover_entrypoints())
    return drivers
