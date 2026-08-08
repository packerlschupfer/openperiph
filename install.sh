#!/bin/sh
set -e

PREFIX="${PREFIX:-/usr/local}"
PYTHON_SITE="${PYTHON_SITE:-$(python3 -c 'import site; print(site.getsitepackages()[0])' 2>/dev/null || echo /usr/lib/python3/dist-packages)}"

echo "Installing openperiph..."
echo "  PREFIX=$PREFIX"
echo "  PYTHON_SITE=$PYTHON_SITE"
echo

# Python package. Modules and drivers are globbed rather than listed
# individually so a newly added driver is picked up automatically.
install -d "$PYTHON_SITE/openperiph/drivers"
for f in src/openperiph/*.py; do
    install -m 644 "$f" "$PYTHON_SITE/openperiph/"
done
for f in src/openperiph/drivers/*.py; do
    install -m 644 "$f" "$PYTHON_SITE/openperiph/drivers/"
done

# CLI + GUI entry points
install -d "$PREFIX/bin"

cat > "$PREFIX/bin/openperiph" << 'SCRIPT'
#!/usr/bin/env python3
from openperiph.cli import main
main()
SCRIPT
chmod 755 "$PREFIX/bin/openperiph"

cat > "$PREFIX/bin/openperiph-gui" << 'SCRIPT'
#!/usr/bin/env python3
from openperiph.gui import main
main()
SCRIPT
chmod 755 "$PREFIX/bin/openperiph-gui"

# udev rules
install -d /etc/udev/rules.d
install -m 644 udev/50-openperiph.rules /etc/udev/rules.d/
udevadm control --reload-rules 2>/dev/null || true
udevadm trigger 2>/dev/null || true

# Desktop entry + icon
install -d "$PREFIX/share/applications"
install -m 644 data/openperiph.desktop "$PREFIX/share/applications/"
install -d "$PREFIX/share/icons/hicolor/scalable/apps"
install -m 644 data/openperiph.svg "$PREFIX/share/icons/hicolor/scalable/apps/openperiph.svg"

echo
echo "Done! You may need to install dependencies:"
echo "  Debian/Ubuntu: sudo apt install python3-usb python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-dbusmenu-glib-0.4"
echo "  Fedora:        sudo dnf install python3-pyusb python3-gobject gtk4 libadwaita libdbusmenu"
echo "  Arch:          sudo pacman -S python-pyusb python-gobject gtk4 libadwaita libdbusmenu-glib"
echo
echo "The udev rules grant access to the logged-in seat user via uaccess -"
echo "re-plug the device (or reboot) for them to take effect."
