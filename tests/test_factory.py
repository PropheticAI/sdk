"""Tests for the factory workflow (build a ready-to-flash install bundle)."""

from __future__ import annotations

import io
import json
import os
import stat
import tarfile
import time

import responses

from prophet.sdk import derive_machine_id
from tests.conftest import BASE_URL, make_jwt

BINARY = b"\x7fELF...prophet-collector-binary"


def _tarball() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="prophet")
        info.size = len(BINARY)
        tar.addfile(info, io.BytesIO(BINARY))
    return buf.getvalue()


def _register_build(base: str, deployment_id: str, machine_id: str) -> None:
    responses.add(
        responses.POST, f"{base}/rest/oauth2/token/1.0",
        json={"access_token": make_jwt(deployment_id), "expires_in": 3600,
              "expires_at": int(time.time()) + 3600, "token_type": "Bearer"},
        status=200,
    )
    responses.add(
        responses.POST, f"{base}/rest/nodes/provision/1.0",
        json={"status": "success", "access_key": "clientid.secretpart",
              "customer_id": deployment_id, "machine_id": machine_id, "profile_id": "prof-1"},
        status=201,
    )
    responses.add(
        responses.GET, f"{base}/rest/collector/download/1.0", body=_tarball(), status=200,
        headers={"content-disposition": "attachment; filename=prophet_v0.3.0_arm7.tar.gz"},
    )


@responses.activate
def test_build_assembles_full_bundle(prophet, tmp_path):
    mid = derive_machine_id("0xABC")
    _register_build(BASE_URL, "john-deere", mid)

    inst = prophet.factory.build(
        deployment_id="john-deere", cpu_id="0xABC", profile_id="prof-1",
        serial="SN-0042", arch="arm7", out_dir=str(tmp_path / "SN-0042"),
    )

    # Installer fields
    assert inst.deployment_id == "john-deere"
    assert inst.machine_id == mid
    assert inst.access_key == "clientid.secretpart"
    assert "secretpart" not in repr(inst)  # secret-safe

    b = inst.bundle_dir
    assert {p.name for p in b.iterdir()} >= {
        "bin", "prophet_collector.yaml", "prophet-node.service", "install.sh", "manifest.json"
    }

    # binary extracted + executable
    binary = b / "bin" / "prophet"
    assert binary.read_bytes() == BINARY
    assert os.stat(binary).st_mode & stat.S_IXUSR

    # yaml carries the right bootstrap config + secure perms
    yaml = (b / "prophet_collector.yaml").read_text()
    assert 'access_key: "clientid.secretpart"' in yaml
    assert f'machine_id: "{mid}"' in yaml
    assert 'profile_id: "prof-1"' in yaml
    assert "spool_dir: /data/apps/prophet/spool" in yaml
    assert oct(os.stat(b / "prophet_collector.yaml").st_mode)[-3:] == "600"

    # systemd unit drives config via the --prophet-dir flag (no env)
    svc = (b / "prophet-node.service").read_text()
    assert "ExecStart=/data/apps/prophet/bin/prophet --prophet-dir /data/apps/prophet/state" in svc
    assert "Environment=" not in svc

    # install.sh encodes the device path/perm contract
    sh = (b / "install.sh").read_text()
    assert "/lib/systemd/system/prophet-node.service" in sh
    assert "systemctl enable --now prophet-node" in sh

    # manifest records identity + integrity
    manifest = json.loads((b / "manifest.json").read_text())
    assert manifest["machine_id"] == mid
    assert manifest["serial"] == "SN-0042"
    assert "sha256" in manifest["files"]["bin/prophet"]


@responses.activate
def test_build_env_matches_dev_client(tmp_path):
    from prophet.sdk import Prophet
    dev = Prophet(base_url="https://dev.prophet.io", client_id="x", client_secret="y")
    mid = derive_machine_id("0xDEV")
    _register_build("https://dev.prophet.io", "child-1", mid)
    inst = dev.factory.build(
        deployment_id="child-1", cpu_id="0xDEV", profile_id="prof-1",
        serial="SN-DEV", out_dir=str(tmp_path / "dev"),
    )
    assert "env: dev" in (inst.bundle_dir / "prophet_collector.yaml").read_text()
