"""Factory API: end-to-end workflows that compose the primitives into one call.

Unlike the API-wrapping namespaces (nodes/deployments/profiles/collector), this is
a workflow layer — `build()` provisions a unit, fetches its binary, and renders a
correct, ready-to-flash install bundle so the manufacturer supplies only domain
facts (end customer, CPU ID, SKU profile, serial), never device implementation
details (paths, perms, args, env).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from ..collector.api import Arch
from .models import Installer

if TYPE_CHECKING:
    from ..client import Prophet


def _systemd_unit(binary_path: str, state_dir: str) -> str:
    return f"""\
[Unit]
Description=Prophet Node
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={binary_path} --prophet-dir {state_dir}
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
"""


def _install_script(install_root: str) -> str:
    # Runs ON the device (over the manufacturer's existing transport). Encodes the
    # full path/permission contract so the operator can't get it wrong.
    return f"""\
#!/bin/sh
set -e
ROOT="{install_root}"
install -D -m755 bin/prophet "$ROOT/bin/prophet"
mkdir -p "$ROOT/state" "$ROOT/spool"
install -m600 prophet_collector.yaml "$ROOT/state/prophet_collector.yaml"
install -m644 prophet-node.service /lib/systemd/system/prophet-node.service
systemctl daemon-reload
systemctl enable --now prophet-node
echo "prophet-node installed and started"
"""


class FactoryAPI:
    """
    Factory provisioning workflow. Accessed via `prophet.factory`.

    Example:
        inst = prophet.factory.build(
            deployment_id="meshcomm-x1234y567",
            cpu_id="0x1122334455667788",
            profile_id="<profile-uuid>",
            serial="SN-0042",
            arch="arm7",
            out_dir="./installers/SN-0042",
        )
        # inst.access_key / inst.machine_id -> ops DB
        # inst.bundle_dir -> copy to the unit, run install.sh
    """

    def __init__(self, client: Prophet) -> None:
        self._client = client

    def build(
        self,
        *,
        deployment_id: str,
        cpu_id: str,
        profile_id: str,
        serial: str,
        arch: Arch = "arm7",
        out_dir: str | Path | None = None,
        install_root: str = "/data/apps/prophet",
        env: Literal["prod", "dev"] | None = None,
        channel: Literal["stable", "dev"] = "stable",
    ) -> Installer:
        """
        Provision a unit and assemble its ready-to-flash install bundle.

        Args:
            deployment_id: child deployment (end-customer) customer_id.
            cpu_id: board hardware CPU ID; derives a deterministic machine_id.
            profile_id: capture-config profile (validated server-side).
            serial: unit serial / asset tag.
            arch: target architecture (default "arm7").
            out_dir: bundle directory (default ./<serial>).
            install_root: device path the unit installs under (default /data/apps/prophet).
            env: device target env; defaults to match the client (prod/dev).
            channel: binary release channel (default "stable").

        Returns:
            Installer with access_key, machine_id, and the bundle directory.
        """
        bundle_dir = Path(out_dir) if out_dir else Path(serial)
        bundle_dir.mkdir(parents=True, exist_ok=True)
        bundle_dir.chmod(0o700)  # holds a secret-bearing yaml

        resolved_env = env or self._env_for_client()
        state_dir = f"{install_root.rstrip('/')}/state"
        spool_dir = f"{install_root.rstrip('/')}/spool"
        device_binary = f"{install_root.rstrip('/')}/bin/prophet"

        # 1. provision the unit (child-scoped access_key + deterministic machine_id)
        unit = self._client.nodes.provision(
            deployment=deployment_id, cpu_id=cpu_id, description=serial, profile_id=profile_id
        )

        # 2. fetch + extract the binary into the bundle
        binary_path = self._client.collector.download(
            arch=arch, channel=channel, extract=True, dest=str(bundle_dir / "bin")
        )

        # 3. render the device contract
        (bundle_dir / "prophet_collector.yaml").write_text(
            unit.collector_yaml(env=resolved_env, spool_dir=spool_dir)
        )
        (bundle_dir / "prophet_collector.yaml").chmod(0o600)
        (bundle_dir / "prophet-node.service").write_text(_systemd_unit(device_binary, state_dir))
        install_sh = bundle_dir / "install.sh"
        install_sh.write_text(_install_script(install_root.rstrip("/")))
        install_sh.chmod(0o755)

        # 4. manifest (records + integrity + file->device-dest map)
        (bundle_dir / "manifest.json").write_text(
            json.dumps(
                self._manifest(unit, serial, cpu_id, deployment_id, arch, install_root, bundle_dir),
                indent=2,
            )
        )

        return Installer(
            deployment_id=deployment_id,
            serial=serial,
            machine_id=unit.machine_id,
            access_key=unit.access_key,
            bundle_dir=bundle_dir,
            binary_path=binary_path,
        )

    def _env_for_client(self) -> Literal["prod", "dev"]:
        return "dev" if "dev.prophet.io" in self._client._base_url else "prod"

    @staticmethod
    def _manifest(
        unit: Any, serial: str, cpu_id: str, deployment_id: str,
        arch: str, install_root: str, bundle_dir: Path,
    ) -> dict[str, Any]:
        root = install_root.rstrip("/")
        files = {
            "bin/prophet": {"dest": f"{root}/bin/prophet", "mode": "0755"},
            "prophet_collector.yaml": {
                "dest": f"{root}/state/prophet_collector.yaml", "mode": "0600",
            },
            "prophet-node.service": {
                "dest": "/lib/systemd/system/prophet-node.service", "mode": "0644",
            },
        }
        for name, meta in files.items():
            meta["sha256"] = _sha256(bundle_dir / name)
        return {
            "serial": serial,
            "cpu_id": cpu_id,
            "machine_id": unit.machine_id,
            "deployment_id": deployment_id,
            "arch": arch,
            "install_root": root,
            "files": files,
        }


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
