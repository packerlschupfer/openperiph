"""
OpenPeriph -- Configuration tool for gaming peripherals on Linux.

Provides a plugin architecture where each device model has its own
protocol driver, while sharing the CLI and GTK4 GUI framework.
"""

__version__ = '0.1.1'

from openperiph.base import PeripheralDevice, DeviceCapabilities

import usb.core
from openperiph.drivers import discover_all


def scan_devices() -> list[PeripheralDevice]:
    """Scan USB for any known peripheral, return instantiated (unopened) drivers."""
    found = []
    for name, cls in discover_all().items():
        caps = cls.capabilities
        for vid, pid in caps.vid_pid_pairs:
            dev = usb.core.find(idVendor=vid, idProduct=pid)
            if dev is not None:
                found.append(cls())
                break
    return found


def find_device(name: str | None = None) -> PeripheralDevice:
    """Find a single peripheral device.

    If *name* is given, only that driver is tried.  Otherwise, scan for
    all known devices and return the first one found.
    Raises RuntimeError if no device is found.
    """
    if name is not None:
        drivers = discover_all()
        cls = drivers.get(name)
        if cls is None:
            avail = ', '.join(sorted(drivers))
            raise RuntimeError(
                f"Unknown device '{name}'. Available: {avail}")
        device = cls()
        return device

    devices = scan_devices()
    if not devices:
        all_drivers = discover_all()
        names = ', '.join(d.capabilities.name for d in all_drivers.values())
        raise RuntimeError(
            f"No supported device found. Supported: {names}")
    return devices[0]
