# Codex instructions

This repository has three independent uv projects. `server/` runs on a Linux host with an NVIDIA GPU; `client/` runs on a Raspberry Pi with a GPIO character LCD; `cpu_gauge/` runs on a Raspberry Pi with a servo needle.

When changing Python dependencies, edit the role's `pyproject.toml` and update its `uv.lock`. Use `uv run --project ROLE` for role specific commands. The official NVIDIA dependency is `nvidia-ml-py`; its import name is `pynvml`.

Keep machine specific values in each role's ignored `config.toml` and document defaults in `config.example.toml`. When adding a required setting, update `install.py` and `README.md` as well. The installer must continue to derive systemd paths and the service user from the installation environment.

The server JSON field names are the contract with both clients. Preserve them or update the affected clients with the server. Hardware behavior needs validation on the NVIDIA host or Raspberry Pi; local tests without those devices can validate config parsing and HTTP behavior only.

After each round of requested changes, run relevant checks and commit the changes made in that round before replying. Leave unrelated user changes out of the commit.
