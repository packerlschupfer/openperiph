"""
Base classes for peripheral device drivers.

Each device model implements a PeripheralDevice subclass with its own protocol.
The GUI and CLI use DeviceCapabilities to adapt dynamically to the hardware.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DeviceCapabilities:
    """Describes what a specific device model supports."""

    name: str                                   # e.g. "Razer DeathAdder V3"
    vid_pid_pairs: list[tuple[int, int]]        # [(0x1532, 0x00B6)]
    interface_num: int                          # USB interface to claim
    report_size: int                            # HID report size in bytes

    num_profiles: int                           # number of onboard profiles
    max_dpi_stages: int                         # max DPI stages per profile
    dpi_min: int                                # lowest DPI value
    dpi_max: int                                # highest DPI value
    dpi_step: int                               # DPI increment step

    buttons: dict[str, int]                     # name -> button_id
    polling_rates: list[int]                    # [125, 250, 500, 1000]
    lod_values: list[int]                       # [1, 2] in mm - or [lo, hi]
                                                 # bounds when lod_step is set
    lod_step: Optional[float] = None

    has_led: bool               = True
    led_effects: list[str]      = field(default_factory=lambda: ['off', 'steady', 'breath'])
    has_breath_speed: bool      = True
    brightness_range: tuple[int, int] = (0, 255)
    breath_speed_range: tuple[int, int] = (0, 100)

    has_angle_snap: bool        = True
    has_ripple_control: bool    = True
    has_motion_sync: bool       = True
    has_debounce: bool          = True
    debounce_range: tuple[int, int] = (0, 20)

    has_stage_colors: bool      = True
    has_reset: bool             = True

    button_labels: dict[str, str] = field(default_factory=dict)


class PeripheralDevice(ABC):
    """Abstract base for all peripheral device drivers.

    Subclasses must define `capabilities` as a class variable and implement
    the required abstract methods.  Optional methods have default
    implementations that raise NotImplementedError -- the GUI/CLI check
    `capabilities.has_*` before calling them.
    """

    capabilities: DeviceCapabilities  # must be set as a class variable

    # -- Connection lifecycle --

    @abstractmethod
    def open(self) -> None:
        """Open the USB device and claim the interface."""

    @abstractmethod
    def close(self) -> None:
        """Release the USB interface and re-attach the kernel driver."""

    # -- Device information --

    def get_firmware_version(self) -> str:
        """Return firmware version string from USB bcdDevice descriptor."""
        return 'unknown'

    # -- Active profile --

    def get_active_profile(self) -> int:
        raise NotImplementedError

    def set_active_profile(self, profile: int) -> None:
        raise NotImplementedError

    # -- Global settings --

    @abstractmethod
    def get_polling_rate(self) -> int: ...

    @abstractmethod
    def set_polling_rate(self, hz: int) -> None: ...

    def get_debounce(self) -> int:
        raise NotImplementedError

    def set_debounce(self, ms: int) -> None:
        raise NotImplementedError

    def get_angle_snap(self) -> bool:
        raise NotImplementedError

    def set_angle_snap(self, enabled: bool) -> None:
        raise NotImplementedError

    def get_ripple_control(self) -> bool:
        raise NotImplementedError

    def set_ripple_control(self, enabled: bool) -> None:
        raise NotImplementedError

    def get_motion_sync(self) -> bool:
        raise NotImplementedError

    def set_motion_sync(self, enabled: bool) -> None:
        raise NotImplementedError

    # -- Per-profile DPI --

    @abstractmethod
    def get_dpi_stages(self, profile: int) -> dict:
        """Return {'active': int, 'count': int, 'stages': [(dpi_x, dpi_y), ...]}."""

    @abstractmethod
    def set_dpi_stages(self, stages: list[int], active: int, profile: int) -> None: ...

    @abstractmethod
    def get_active_dpi_stage(self, profile: int) -> int: ...

    @abstractmethod
    def set_active_dpi_stage(self, stage: int, profile: int) -> None: ...

    # -- Per-profile optional settings --

    def get_lod(self, profile: int) -> float:
        raise NotImplementedError

    def set_lod(self, mm: float, profile: int) -> None:
        raise NotImplementedError

    def get_brightness(self, profile: int) -> int:
        raise NotImplementedError

    def set_brightness(self, value: int, profile: int) -> None:
        raise NotImplementedError

    def get_led_effect(self, profile: int) -> str:
        raise NotImplementedError

    def set_led_effect(self, effect: str, profile: int) -> None:
        raise NotImplementedError

    def get_breath_speed(self, profile: int) -> int:
        raise NotImplementedError

    def set_breath_speed(self, speed: int, profile: int) -> None:
        raise NotImplementedError

    def get_stage_color(self, stage: int, profile: int) -> tuple[int, int, int]:
        raise NotImplementedError

    def set_stage_color(self, stage: int, r: int, g: int, b: int, profile: int) -> None:
        raise NotImplementedError

    def get_button(self, btn_id: int, profile: int) -> tuple[int, int, int]:
        """Return (type, action1, action2) raw bytes."""
        raise NotImplementedError

    def set_button(self, btn_id: int, btn_type: int, a1: int, a2: int,
                   profile: int) -> None:
        raise NotImplementedError

    # -- Button encoding --
    #
    # The (type, a1, a2) triple get_button/set_button deal in is the
    # *device's* encoding, so turning it into text -- and back -- is the
    # driver's business, not the framework's. These defaults are the
    # Pulsar/Sonix tables in hid.py, which every driver written so far
    # shares. A device whose encoding differs overrides these two rather
    # than translating itself into Sonix's scheme to satisfy the framework
    # (which is what drivers/nordic.py's _NORDIC_MOUSE_TO_SONIX does).
    #
    # The two must round-trip: parse_button_function(describe_button(t, a1,
    # a2)) == (t, a1, a2) for anything the device can hold, since that pair
    # is what profile export/import moves through JSON.

    def describe_button(self, btn_type: int, a1: int, a2: int) -> str:
        """Human-readable description of a raw button binding."""
        from openperiph.hid import describe_button
        return describe_button(btn_type, a1, a2)

    def parse_button_function(self, spec: str) -> tuple[int, int, int]:
        """Parse a description back into this device's (type, a1, a2)."""
        from openperiph.hid import parse_button_function
        return parse_button_function(spec)

    def button_function_names(self) -> list[str]:
        """Every spec string parse_button_function() accepts, for UI pickers."""
        from openperiph import hid
        return (['disabled', 'xclick']
                + list(hid.MOUSE_ACTIONS) + list(hid.SCROLL_ACTIONS)
                + list(hid.DPI_ACTIONS) + list(hid.PROFILE_ACTIONS)
                + list(hid.MEDIA_CODES))

    def reset_to_defaults(self, profile: int) -> None:
        raise NotImplementedError

    # -- Hidraw (for tray / DPI notifications) --

    def find_hidraw(self) -> Optional[str]:
        """Return /dev/hidrawN path for DPI event listening, or None."""
        return None

    def parse_hidraw_event(self, data: bytes) -> Optional[dict]:
        """Parse a hidraw event. Return {'dpi': int, 'stage': int} or None."""
        return None

    # -- Profile import / export --

    def export_profile(self, profile: int) -> dict:
        """Read all per-profile settings and return as a serialisable dict."""
        caps = self.capabilities
        data = {
            'format': 'openperiph-profile',
            'version': 1,
            'device': caps.name,
            'profile': profile,
        }
        try:
            info = self.get_dpi_stages(profile)
            data['dpi'] = {
                'active': info['active'],
                'stages': [dx for dx, _dy in info['stages'][:info['count']]],
            }
        except Exception:
            pass
        if caps.has_stage_colors:
            try:
                colors = []
                stages = data.get('dpi', {}).get('stages')
                n = len(stages) if stages else caps.max_dpi_stages
                for i in range(1, n + 1):
                    colors.append(list(self.get_stage_color(i, profile)))
                data['stage_colors'] = colors
            except Exception:
                pass
        if caps.lod_values:
            try:
                data['lod_mm'] = self.get_lod(profile)
            except Exception:
                pass
        if caps.has_led:
            try:
                data['brightness'] = self.get_brightness(profile)
            except Exception:
                pass
            try:
                data['led_effect'] = self.get_led_effect(profile)
            except Exception:
                pass
            if caps.has_breath_speed:
                try:
                    data['breath_speed'] = self.get_breath_speed(profile)
                except Exception:
                    pass
        try:
            buttons = {}
            for name, bid in caps.buttons.items():
                t, a1, a2 = self.get_button(bid, profile)
                buttons[name] = self.describe_button(t, a1, a2)
            data['buttons'] = buttons
        except Exception:
            pass
        return data

    def import_profile(self, profile: int, data: dict) -> list[str]:
        """Apply profile settings from a dict. Returns list of warnings."""
        caps = self.capabilities
        warnings = []
        if 'dpi' in data:
            try:
                dpi = data['dpi']
                self.set_dpi_stages(dpi['stages'], dpi.get('active', 1), profile)
            except Exception as e:
                warnings.append(f'DPI: {e}')
        if 'stage_colors' in data and caps.has_stage_colors:
            for i, rgb in enumerate(data['stage_colors'], 1):
                try:
                    self.set_stage_color(i, rgb[0], rgb[1], rgb[2], profile)
                except Exception as e:
                    warnings.append(f'Stage {i} color: {e}')
        if 'lod_mm' in data and caps.lod_values:
            try:
                self.set_lod(data['lod_mm'], profile)
            except Exception as e:
                warnings.append(f'LOD: {e}')
        if 'brightness' in data and caps.has_led:
            try:
                self.set_brightness(data['brightness'], profile)
            except Exception as e:
                warnings.append(f'Brightness: {e}')
        if 'led_effect' in data and caps.has_led:
            try:
                self.set_led_effect(data['led_effect'], profile)
            except Exception as e:
                warnings.append(f'LED effect: {e}')
        if 'breath_speed' in data and caps.has_led and caps.has_breath_speed:
            try:
                self.set_breath_speed(data['breath_speed'], profile)
            except Exception as e:
                warnings.append(f'Breath speed: {e}')
        if 'buttons' in data:
            for name, func_str in data['buttons'].items():
                bid = caps.buttons.get(name)
                if bid is None:
                    warnings.append(f'Button "{name}" not found on this device')
                    continue
                try:
                    t, a1, a2 = self.parse_button_function(func_str)
                    self.set_button(bid, t, a1, a2, profile)
                except Exception as e:
                    warnings.append(f'Button {name}: {e}')
        return warnings
