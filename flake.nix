{
  description = "Linux configuration tool for gaming peripherals (Pulsar X2A/X2H/X2/Xlite, Feinmann FO1, Nordic)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = self.packages.${system}.openperiph;

          openperiph = pkgs.python3Packages.buildPythonApplication {
            pname = "openperiph";
            version = "0.1.1";
            pyproject = true;

            src = self;

            build-system = [ pkgs.python3Packages.setuptools ];

            dependencies = [
              pkgs.python3Packages.pyusb
              pkgs.python3Packages.pygobject3
            ];

            nativeBuildInputs = [
              pkgs.wrapGAppsHook4
              pkgs.gobject-introspection
            ];

            buildInputs = [
              pkgs.gtk4
              pkgs.libadwaita
              pkgs.libdbusmenu
            ];

            # udev rules aren't picked up automatically from a Python build;
            # ship them under lib/udev/rules.d so services.udev.packages
            # (NixOS) or the package's own postinstall hook (other distros)
            # can find them. Desktop file/icon likewise aren't part of the
            # Python package itself -- and the icon has to land in hicolor
            # for the GUI's Home page to resolve it by name (gui.py's
            # _logo_image() falls back to the source tree otherwise).
            postInstall = ''
              install -Dm444 udev/50-openperiph.rules $out/lib/udev/rules.d/50-openperiph.rules
              install -Dm444 data/openperiph.desktop $out/share/applications/openperiph.desktop
              install -Dm444 data/openperiph.svg $out/share/icons/hicolor/scalable/apps/openperiph.svg
            '';

            meta = {
              description = "Linux configuration tool for gaming peripherals";
              homepage = "https://github.com/packerlschupfer/openperiph";
              license = pkgs.lib.licenses.mit;
              mainProgram = "openperiph-gui";
              platforms = pkgs.lib.platforms.linux;
            };
          };
        }
      );

      # For consumers who'd rather bring this into their own nixpkgs instance
      # (e.g. `nixpkgs.overlays = [ openperiph.overlays.default ]`) than
      # reference `packages.<system>.default` directly.
      overlays.default = final: prev: {
        openperiph = self.packages.${prev.system}.openperiph;
      };

      apps = forAllSystems (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/openperiph-gui";
        };
        cli = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/openperiph";
        };
      });
    };
}
