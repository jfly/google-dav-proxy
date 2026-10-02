{ inputs, lib, ... }:
{
  imports = [
    ./uv2nix.nix
    inputs.devshell.flakeModule
  ];

  perSystem =
    { pkgs, ... }:
    {
      uv2nix = {
        python = pkgs.python313;

        workspaceRoot = ./..;
      };
    };
}
