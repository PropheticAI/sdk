"""Data models for the factory workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Installer:
    """
    A ready-to-flash install bundle for one unit, produced by `prophet.factory.build()`.

    `access_key` is the per-unit secret (shown once) — store it in your ops DB
    keyed by serial/machine_id. `bundle_dir` holds the binary + config + systemd
    unit + install.sh; copy it to the unit and run install.sh.
    """

    deployment_id: str
    serial: str
    machine_id: str
    access_key: str
    bundle_dir: Path
    binary_path: Path

    def __repr__(self) -> str:
        # Never echo the secret half of the access_key.
        client_id = self.access_key.split(".", 1)[0]
        return (
            f"Installer(serial={self.serial!r}, machine_id={self.machine_id!r}, "
            f"client_id={client_id!r}, bundle_dir={str(self.bundle_dir)!r})"
        )
