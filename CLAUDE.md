# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenPeriph is a Linux configuration tool for gaming peripherals (mice, keyboards). Plugin architecture: each device model ships its own USB protocol driver, while the CLI, GTK4/libadwaita GUI, and system tray are generic and adapt at runtime to `device.capabilities`.

The framework and its seven drivers were ported from [pulsar-mouse-linux](https://github.com/packerlschupfer/pulsar-mouse-linux) (working copy at `/home/mrnice/git/github/pulsar-mouse-linux`) — same code with `pulsar_mouse` → `openperiph` and `PulsarDevice` → `PeripheralDevice` renames. That repo is still the place to check when a behaviour here looks odd; it has the longer commit history behind the protocol work.

**Port from `packerlschupfer/pulsar-mouse-linux` — it is the original and canonical repo.** `harveywuk/pulsar-mouse-linux` is a fork of it (first commit 2026-08-07, two months after the initial release) whose work — the Feinmann 8K driver, most of the GUI — is adopted back into the canonical repo selectively and credited in its README. It is not an upstream, and the `harveywuk` git remote in that checkout does not make it one. Two separate sessions read the remote plus the "Adopt harveywuk's latest" commit subject and concluded the hierarchy ran the other way; both were wrong, in both directions.

## Build & Validate

Pure Python — no compilation step, no unit tests.

```bash
# Syntax check
for f in src/openperiph/*.py src/openperiph/drivers/*.py; do python3 -m py_compile "$f"; done

# Backend import check (what CI runs)
PYTHONPATH=src python3 -c "
from openperiph import scan_devices, find_device, __version__
from openperiph.drivers import discover_all
print(__version__, list(discover_all()))"

# GUI import check — works headless, no display needed
PYTHONPATH=src python3 -c "import openperiph.gui"

# Run (requires a real device, plus sudo or udev rules)
PYTHONPATH=src python3 -m openperiph.cli
PYTHONPATH=src python3 -m openperiph.gui

# Or install in dev mode
pip install --user -e .   # provides `openperiph` and `openperiph-gui`
```

CI (`.github/workflows/ci.yml`) runs exactly the checks above on Ubuntu 24.04.

With hardware plugged in, the real end-to-end check is a CLI read — it exercises discovery, `open()`, every getter, and `close()`:

```bash
PYTHONPATH=src python3 -m openperiph.cli --profile 1
```

**After touching any driver's transport, and when adding a driver, run the soak:**

```bash
PYTHONPATH=src python3 tools/protocol-soak.py --rounds 8
```

It replays the burst of writes the GUI's Apply performs, reports how many survive, restores the state it captured, and exits non-zero on any failure or drift. It needs real hardware so it is not in CI. Interactive testing does not catch transport bugs — both driver bugs found so far (`_poll_ack`, the LED block) only appear under back-to-back traffic.

## Release Process

Tag `vX.Y.Z` and push. `.github/workflows/release.yml` builds .deb, .rpm, tarball, and AppImage artifacts and attaches them to the release. `install.sh` does the same layout for a local system-wide install (`sudo ./install.sh`, honours `PREFIX`/`PYTHON_SITE`).

All four packaging paths glob `src/openperiph/*.py` and `src/openperiph/drivers/*.py` rather than listing modules — a new driver file needs no packaging change (upstream listed files individually and the list went stale). The .deb deliberately declares no `Replaces:`/`Conflicts:` against `pulsar-mouse-linux`: the two install disjoint paths and binaries, so they can coexist.

## Architecture

### Package layout (`src/openperiph/`)

- **`base.py`** — `DeviceCapabilities` dataclass + `PeripheralDevice` ABC. Also holds the generic `export_profile()` / `import_profile()` JSON round-trip, which is capability-gated and driver-agnostic.
- **`hid.py`** — Device-independent button/HID tables: function type constants (`BTN_TYPE_*`), mouse/scroll/DPI/profile/media action maps, HID keycodes and modifiers, plus `describe_button()` and `parse_button_function()`.
- **`drivers/__init__.py`** — `discover_all()`: two-tier discovery, scanning built-in submodules via `pkgutil.iter_modules` then merging `importlib.metadata.entry_points(group='openperiph.drivers')` on top. The submodule scan only registers classes whose `__module__` is the module being scanned, so a thin driver that imports its protocol parent doesn't accidentally register the parent under its own name.
- **`drivers/*.py`** — Seven drivers in three families: `x2a.py` (Sonix 64-byte feature reports) with four thin subclasses, `feinmann8k.py` (wireless dongle, same framing plus ack-polling reads), `nordic.py` (flat memory map over interrupt endpoints).
- **`__init__.py`** — Public API: `scan_devices()`, `find_device(name=None)`, `__version__`.
- **`cli.py`** — Generic argparse CLI. Flags exist unconditionally; *output and behaviour* are gated on `caps.has_*`. Also has `--battery-json` / `--status-json` machine-readable modes for scripts and status bars.
- **`gui.py`** — Generic GTK4/libadwaita GUI (~2600 lines): sidebar nav (Home / Performance / Customize / Tools / Power), D-Bus StatusNotifierItem tray with Dbusmenu, hidraw DPI/battery listener, button remap dialog, input test dialog.

### Capability-driven UI

`DeviceCapabilities` is a **class variable** on each driver, not an instance attribute — `scan_devices()` reads `cls.capabilities.vid_pid_pairs` to match VID/PID *without instantiating or opening* the device. Never move it into `__init__`.

The CLI and GUI never hardcode a device's feature set. They check `caps.has_led`, `caps.has_debounce`, `caps.lod_values`, `caps.num_profiles`, etc., and skip the corresponding rows/output when false. A driver that doesn't support something sets the flag false and simply doesn't override the method (the ABC default raises `NotImplementedError`).

### Optional methods outside the ABC

Wireless-only features are gated by `hasattr(device, ...)` rather than by a capability flag or an ABC method — there is no `has_battery` field. A driver opts in by simply defining:

- `get_power()` → `{'battery_percent': int, 'power_connected': bool, 'battery_mv': int|None}` — drives the tray battery item, Home page battery row, `--battery-json`, and the tray "Signal" item.
- `get_power_saving_timeout()` / `set_power_saving_timeout(seconds)` — 30–900 s, GUI Power page slider.
- `get_low_power_threshold()` / `set_low_power_threshold(percent)` — 0–100 %, GUI Power page slider.

The 30–900 / 0–100 bounds are hardcoded in both `cli.py` and `gui.py`; there is no capability constant for them. Follow the same `hasattr` pattern for any other feature only some devices have, or promote it to `DeviceCapabilities` if it becomes common.

`find_hidraw()` / `parse_hidraw_event()` are ABC methods with `None`-returning defaults — override them for devices that push DPI-change or signal-quality events. Note that `find_hidraw()` having a base implementation means it is *not* a reliable "is wireless" test; `get_power` is what the GUI uses for that.

### GUI threading model

All USB I/O happens on background threads serialised by the module-level `_USB_LOCK` (`threading.Lock`). Rules:

1. GUI callbacks snapshot widget values on the main thread, then hand them to a worker (`_run_bg`).
2. Workers take `_USB_LOCK`, do USB reads/writes, and push results back via `GLib.idle_add(...)`. Never touch widgets directly from a thread.
3. `self._building` suppresses change callbacks while widgets are being populated from device state — check it at the top of every `_on_*_changed` handler.
4. The tray hidraw listener (`OpenPeriphApp._hidraw_listener`) and the Home page listener (`MainWindow._home_hidraw_listener`) are deliberately separate daemon threads, not shared.

Reads happen on **Reload**, writes on **Apply** — the GUI does not write through on every widget change.

## Writing a Driver

The whole point of the repo. Pick the in-repo driver closest to your case and copy its shape:

| File | Pattern to copy |
|---|---|
| `x2a.py` (350 lines) | Full standalone driver — 64-byte HID Feature Reports, `_build`/`_read`/`_cmd` helpers, LE uint16 checksum, encoding tables, factory-default button map |
| `xlite_wired.py`, `x2h.py`, `x2_wired.py`, `xlite_v4.py` (~50 lines each) | Same protocol, different model: subclass the protocol driver and override only `capabilities` |
| `feinmann8k.py` (711 lines) | Wireless: `get_power()`, power-saving/low-power methods, hidraw signal-quality parsing, ack-polling reads. Its module docstring documents the RF-latency polling loop in detail — read it before touching any wireless read path |
| `nordic.py` (497 lines) | Different chipset entirely — flat memory map over interrupt endpoints instead of feature reports |

Steps:

1. Create `src/openperiph/drivers/yourdevice.py`.
2. Subclass `PeripheralDevice`; set `capabilities = DeviceCapabilities(...)` as a class variable.
3. Implement `open()`/`close()` (detach kernel driver, claim interface, and re-attach on close) plus the abstract methods: `get/set_polling_rate`, `get/set_dpi_stages`, `get/set_active_dpi_stage`.
4. Override the optional getters/setters the device actually supports, and set the matching `has_*` flags. Keep all register addresses, offsets, and encoding tables **in the driver file** — nothing device-specific belongs in `base.py`, `hid.py`, `cli.py`, or `gui.py`.
5. Add both a `SUBSYSTEM=="usb"` and a `KERNEL=="hidraw*"` line for the VID/PID to `udev/50-openperiph.rules`. Note it uses `ATTRS{}` (not `ATTR{}`) plus `MODE="0660"` and `TAG+="uaccess"`, and deliberately sets no `GROUP` — a rule naming a group the distro doesn't have is discarded *in its entirety*, silently taking `MODE` and `TAG` with it.
6. Register in `pyproject.toml` under `[project.entry-points."openperiph.drivers"]`. Built-in submodule scanning already finds it; entry points matter for external driver packages and for installs that bypass pip.
7. Add a row to the README's Supported Devices table. Mark it Untested unless you have the hardware — `xlite_v4` and `nordic` say `Status: UNTESTED` in their own docstrings and the table matches them (upstream's README claims `nordic` is supported; its code disagrees, and the code wins here).

Each driver owns its USB handle internally (`self._dev`) — handles are never passed around.

Adding a *new setting* to an existing driver: encoding constants + `get_X()`/`set_X()` in the driver → if it's cross-device, add the ABC method in `base.py` and a `has_X` field in `DeviceCapabilities` → wire into `cli.py` argparse and printing → add a capability-gated `Adw.PreferencesRow` in `gui.py`.

## Known Gaps

- `hid.py`'s tables are the Pulsar/Sonix button encoding even though the module is named generically. The keyboard and media codes are genuinely HID-standard; the `BTN_TYPE_*` values and action tables are not. A new vendor whose encoding differs should keep its own tables in its driver rather than bending these.
- `DeviceCapabilities` is mouse-shaped (DPI stages, LOD, angle snap) — the README promises keyboards but nothing models them yet. Add keyboard fields as optional-with-defaults so existing drivers keep constructing.
- Every device supported so far is Pulsar-VID (`0x3710`/`0x3554`) apart from Feinmann, which shares Pulsar's VID and framing. The multi-manufacturer claim is untested against a genuinely foreign protocol (Razer, Logitech).
- `flake.nix` is ported but **unvalidated** — there is no nix on this machine, so it has never been built. `flake.lock` is upstream's, which is sound because the input set is identical (one nixpkgs input, same URL). There is no FlakeHub publish workflow; if one is added, trigger it on **tags only**, never on pushes to main — FlakeHub derives its version from the commit count, so republishing the same count collides.
- `nordic.py` and `xlite_v4.py` have never run against hardware.

## Dependencies

- `pyusb` (`python3-usb`) — USB communication
- `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1` — GUI
- `gir1.2-dbusmenu-glib-0.4` — system tray menu

## Key Constraints

- Device access needs sudo or the udev rules in `udev/50-openperiph.rules`.
- `capabilities` must stay a class variable (see above).
- Profile numbers are 1-based throughout (`1..caps.num_profiles`); DPI stage indices are 1-based too.
- Profile JSON files are tagged `"format": "openperiph-profile"` — `cli.py --import` rejects anything else, so pulsar-mouse-linux exports are not directly loadable.
