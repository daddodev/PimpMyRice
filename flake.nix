{
  description = "A Nix-flake-based Python development environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
  inputs.docopt-completion.url = "path:/home/shobu/Workspace/docopt-completion";

  outputs = { self, nixpkgs, docopt-completion }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forEachSupportedSystem = f: nixpkgs.lib.genAttrs supportedSystems (system: f rec {
        pkgs = import nixpkgs { inherit system; };
        pythonPackages = (with pkgs.python312Packages; [
          docopt
          jinja2
          pyyaml
          psutil
          requests
          scikit-learn
          opencv-python
          rich
          typing-extensions
          pydantic
          pydantic-extra-types
          numpy
        ]);
        pythonPackagesDev = (with pkgs.python312Packages; [
          pytest
          pytest-asyncio
          mypy
          black
          types-requests
          types-pyyaml
          isort
        ]);
      });
    in
    {
      packages = forEachSupportedSystem ({pkgs, pythonPackages, ...}: rec {
        default = pkgs.python312Packages.buildPythonApplication rec {
          pname = "pimpmyrice";
          version = "0.3.0";

          src = pkgs.fetchPypi {
            inherit pname version;
            hash = "sha256-J+V2GWHqJiGd931AOW00bNx3cAjumR72+kw7e3+tNxg=";
          };

          pyproject = true;

          build-system = with pkgs.python312Packages; [
            setuptools
          ];

          dependencies = [pythonPackages] ++ [docopt-completion.packages.${pkgs.system}.default];
        };

        pimpmyrice = default;
      });

      devShells = forEachSupportedSystem ({ pkgs, pythonPackages, pythonPackagesDev }: {
        default = pkgs.mkShell {
          venvDir = ".venv";
          packages = with pkgs; [ python312 docopt-completion.packages.${system}.default ] ++
            (with pkgs.python312Packages; [
              pip
              venvShellHook
            ] ++
            pythonPackages ++
            pythonPackagesDev);
        };
      });
    };
}
