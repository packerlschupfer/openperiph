# OpenPeriph

Linux configuration tool for **gaming peripherals** — mice, keyboards, and more.

GTK4/libadwaita GUI with a plugin architecture: each device model has its own
protocol driver, while sharing the settings UI, CLI, and system tray applet.
The interface adapts dynamically to the connected device's capabilities.

## Supported Devices

| Manufacturer | Model | Driver | VID:PID | Status |
|---|---|---|---|---|
| Pulsar | Xlite Wired | `xlite_wired` | `3710:1401` | Supported (Sonix, 50 DPI step) |
| Pulsar | X2 Wired | `x2_wired` | `3710:1402` | Supported (Sonix) |
| Pulsar | X2H Wired Medium | `x2h` | `3710:1403` | Fully supported |
| Pulsar | X2A Medium Wired | `x2a` | `3710:1404` | Fully supported |
| Pulsar | Xlite v4 | `xlite_v4` | `3710:3401` | Untested (same Sonix protocol) |
| Pulsar | X2A Wireless / X2 V2 Mini | `nordic` | `3554:f507` `3554:f508` | Untested (Nordic chipset, battery status) |
| Feinmann | FO1 / 8K dongle | `feinmann8k` | `3710:5404` | Fully supported (wireless, 8K Hz polling, 6 onboard profiles) |

Want to add support for your device? See [Writing a driver](#writing-a-driver) below.

## Requirements

**Debian / Ubuntu:**
```bash
sudo apt install python3-usb python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-dbusmenu-glib-0.4
```

**Fedora:**
```bash
sudo dnf install python3-pyusb python3-gobject gtk4 libadwaita libdbusmenu
```

**Arch Linux:**
```bash
sudo pacman -S python-pyusb python-gobject gtk4 libadwaita libdbusmenu-glib
```

On GNOME you also need the AppIndicator shell extension for the tray icon:
```bash
sudo apt install gnome-shell-extension-appindicator   # Debian/Ubuntu
gnome-extensions enable ubuntu-appindicators@ubuntu.com
```

KDE Plasma & Hyprland support the system tray natively.

## Installation

### From git

```bash
git clone https://github.com/packerlschupfer/openperiph
cd openperiph
pip install --user -e .
```

### System-wide (no pip)

```bash
sudo ./install.sh          # honours PREFIX / PYTHON_SITE env vars
```

Installs the Python package, both entry points, the udev rules, and the
desktop entry + icon. Tagged releases also ship .deb, .rpm, tarball, and
AppImage builds.

### Nix

```bash
nix run github:packerlschupfer/openperiph          # GUI
nix run github:packerlschupfer/openperiph#cli      # CLI
```

Or add the flake's `overlays.default` to your own nixpkgs. On NixOS, put the
package in `services.udev.packages` to pick up its device rules.

### Run without installing

```bash
PYTHONPATH=src python3 -m openperiph.gui    # GUI
PYTHONPATH=src python3 -m openperiph.cli    # CLI
```

### udev rules

```bash
sudo cp udev/50-openperiph.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

## GUI

```bash
openperiph-gui
```

GTK4 + libadwaita settings window with integrated system tray:
- Auto-detects connected device and adapts UI to its capabilities
- Reads all settings from the device on startup, writes on **Apply**
- System tray via D-Bus StatusNotifierItem (no GTK3 conflict)
- Tray shows DPI/polling rate on change, quick DPI presets, polling rate radio buttons
- **X** hides the window (tray stays alive), **Quit** from tray menu exits

## CLI

```bash
openperiph                              # show all settings
openperiph --profile 1                  # show profile 1 only
openperiph --poll 1000                  # set polling rate
openperiph --profile 1 --dpi 400,800,1600
openperiph --profile 1 --button thumb1 dpi+
openperiph --profile 1 --export profile1.json
```

## Writing a driver

Each device model uses a different USB protocol. To add support for a new device:

1. Create `src/openperiph/drivers/yourdevice.py`
2. Subclass `PeripheralDevice` from `openperiph.base`
3. Define `capabilities` as a class variable (a `DeviceCapabilities` dataclass)
4. Implement the protocol methods (`open`, `close`, `get/set_polling_rate`, `get/set_dpi_stages`, etc.)
5. Add an entry point in `pyproject.toml`:
   ```toml
   [project.entry-points."openperiph.drivers"]
   yourdevice = "openperiph.drivers.yourdevice:YourClass"
   ```
6. Add udev rules for the new VID/PID in `udev/50-openperiph.rules`

The CLI and GUI will automatically detect the new driver and adapt their UI.

External driver packages can also register via entry points without modifying this repo.

## Architecture

### Package layout (`src/openperiph/`)

- **`base.py`** — `DeviceCapabilities` dataclass and `PeripheralDevice` ABC
- **`hid.py`** — Shared HID constants: button function types, action tables, keyboard/media codes
- **`drivers/__init__.py`** — Two-tier driver discovery: built-in submodules + `importlib.metadata.entry_points`
- **`drivers/*.py`** — One protocol driver per device family; thin models subclass a family's driver and override only `capabilities`
- **`__init__.py`** — Public API: `scan_devices()`, `find_device()`, version
- **`cli.py`** — Generic argparse CLI, adapts to `device.capabilities`
- **`gui.py`** — Generic GTK4/libadwaita GUI, builds UI dynamically from capabilities

### Plugin system

External driver packages register via Python entry points:
```toml
[project.entry-points."openperiph.drivers"]
mydriver = "my_package.driver:MyDevice"
```

## Credits

The framework, drivers and GUI were ported from
[pulsar-mouse-linux](https://github.com/packerlschupfer/pulsar-mouse-linux),
which carries these credits:

- [@harveywuk](https://github.com/harveywuk) — Feinmann 8K/FO1 driver, GUI redesign, button remapping, Hyprland/KDE pointer-settings integration
- [@Scout339](https://github.com/Scout339) — Logo design (`data/openperiph.svg`), wireless mouse testing
- [andrewrabert](https://github.com/andrewrabert) — [python-pulsar-mouse-tool](https://github.com/andrewrabert/python-pulsar-mouse-tool), reference implementation for the Nordic wireless protocol

## License

MIT
