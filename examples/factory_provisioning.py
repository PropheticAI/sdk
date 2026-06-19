"""
Prophet factory provisioning — reference integration for a manufacturing line.

This is the end-to-end pattern a hardware manufacturer (an MSP) follows to ship
units that come pre-enrolled in Prophet, with no human approval and no field
setup. It covers the full lifecycle:

  1. onboard an end customer   -> create a child deployment            (once per customer)
  2. define a fleet profile    -> capture config for a hardware type   (once per hardware SKU)
  3. provision each unit        -> per-unit credential + device config  (per unit, on the line)
  4. verify enrollment          -> poll until the unit reports in       (the build pass/fail gate)
  5. off-board an end customer   -> delete a child deployment + its units (as needed)

Identity & re-flash: each unit is keyed by a `machine_id` the SDK derives
deterministically from the board's CPU ID, so re-flashing the same board
re-attaches to its existing node record instead of creating a duplicate.
Re-running provision() for the same CPU ID mints a NEW access_key (the previous
one stays valid until the node is deleted) — so the cleanest factory practice is
to store each unit's rendered config in your ops DB keyed by serial/CPU ID and
just re-copy it when you re-flash; only call provision() again for a genuinely
new board.

Zero-touch: provisioning with an access_key (what this example does) enrolls
units as 'active' immediately — no pending-approval/staged step — which is what
delivers hands-off enrollment on the line.

Authentication: a parent (MSP) API client credential. Configure via environment:

    PROPHET_BASE_URL      # default https://app.prophet.io
    PROPHET_CLIENT_ID
    PROPHET_CLIENT_SECRET

One-time setup (creates a child deployment + fleet profile, prints the two IDs):

    PROPHET_CLIENT_ID=... PROPHET_CLIENT_SECRET=... \
    python examples/factory_provisioning.py --setup --customer "Acme Corp" --handle acme

Per-unit provisioning on the build line (reuses those IDs):

    PROPHET_CLIENT_ID=... PROPHET_CLIENT_SECRET=... \
    PROPHET_DEPLOYMENT_ID=<child-customer-id> PROPHET_PROFILE_ID=<profile-id> \
    python examples/factory_provisioning.py --cpu-id 0x1122334455667788 --serial SN-0042
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from prophet.sdk import Prophet, ProvisionedUnit
from prophet.sdk.profiles import lightweight_packet_services

# State root on the device. Pointing PROPHET_DIR at a directory on the unit's
# OTA-persistent partition (here /data/apps/prophet) keeps the config AND the
# enrollment credential alive across firmware updates that replace the rootfs.
# Requires a prophet-node build with PROPHET_DIR support.
DEVICE_STATE_DIR = "/data/apps/prophet/state"
DEVICE_SPOOL_DIR = "/data/apps/prophet/spool"

# The systemd unit the build line installs at /lib/systemd/system/. ExecStart is
# bare — the binary reads all bootstrap config from prophet_collector.yaml under
# PROPHET_DIR. Runs as root for packet capture; Restart=always lets a unit
# flashed offline self-enroll once it first reaches a network.
SYSTEMD_UNIT = f"""\
[Unit]
Description=Prophet Node
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=PROPHET_DIR={DEVICE_STATE_DIR}
ExecStart=/data/apps/prophet/bin/prophet
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
"""


# ── 1. Onboard an end customer (once per customer) ──────────────────────────
def onboard_end_customer(prophet: Prophet, name: str, handle: str) -> str:
    """Create a child deployment under the authenticated parent. Returns its customer_id."""
    parent_id = prophet.deployments.list().parent.customer_id
    created = prophet.deployments.create(name=name, handle=handle, parent_id=parent_id)
    return created.deployment.customer.customer_id


# ── 2. Define a fleet capture profile (once per hardware SKU) ────────────────
def create_fleet_profile(prophet: Prophet, name: str, interface_patterns: list[str]) -> str:
    """
    Create a low-footprint capture profile suited to constrained edge units (e.g.
    ~490MB ARM boards). Units inherit it at first boot. Returns profile_id.

    You typically create one profile per hardware SKU and reuse its profile_id
    across every customer deployment that ships that SKU. fleet_staging is left at
    its default (False): combined with access_key provisioning, units enroll as
    'active' with no approval step — the mechanism behind zero-touch enrollment.
    """
    profile = prophet.profiles.create(
        name=name,
        description="Edge fleet capture profile",
        services=lightweight_packet_services(interface_patterns=interface_patterns),
    )
    return profile.profile_id


# ── 3. Provision a unit (per unit, on the build line) ───────────────────────
def provision_unit(
    prophet: Prophet,
    *,
    deployment: str,
    cpu_id: str,
    serial: str,
    profile_id: str,
    out_dir: Path,
) -> ProvisionedUnit:
    """
    Mint a per-unit credential and write the two files the line copies onto the
    device. The access_key is a secret shown exactly once — store it in your ops
    DB keyed by serial/CPU ID, and write it only into the device config (never log it).
    """
    unit = prophet.nodes.provision(
        deployment=deployment,
        cpu_id=cpu_id,
        description=serial,
        profile_id=profile_id,
    )

    # The output dir holds a secret-bearing file; keep it private.
    out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(out_dir, 0o700)

    # prophet_collector.yaml -> $PROPHET_DIR/prophet_collector.yaml on the device.
    # Holds the secret access_key, so write it 0600.
    yaml_path = out_dir / "prophet_collector.yaml"
    yaml_path.write_text(unit.collector_yaml(env="prod", spool_dir=DEVICE_SPOOL_DIR))
    os.chmod(yaml_path, 0o600)

    # prophet-node.service -> /lib/systemd/system/ on the device.
    (out_dir / "prophet-node.service").write_text(SYSTEMD_UNIT)

    return unit


# ── 4. Verify enrollment (the build-line pass/fail gate) ────────────────────
def wait_for_enrollment(prophet: Prophet, machine_id: str, timeout_s: int = 180) -> bool:
    """
    Poll until the unit has booted, enrolled, and reported in. True once the node
    is active with a live control-plane connection — the signal to clear the unit
    for shipping (the manufacturing 'service verification' step).

    The gate keys on machine_id (the controller-assigned node_id isn't known until
    first boot). find_by_machine_id scans the node list, so run this gate right
    after a unit boots rather than as a batch sweep over a large fleet.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        node = prophet.nodes.find_by_machine_id(machine_id)
        if node and node.is_enrolled:
            return True
        time.sleep(5)
    return False


# ── 5. Off-board an end customer (delete a child deployment) ─────────────────
def off_board_end_customer(prophet: Prophet, customer_id: str) -> None:
    """
    Delete a child deployment. This removes the end customer AND cascades deletion
    of ALL of their units' node records and credentials — it is NOT a per-unit RMA.

    The SDK does not yet expose single-unit deletion. To retire one unit, delete
    it from the Prophet console; to replace a failed board, provision the new board
    (a new CPU ID is simply a new unit).
    """
    parent_id = prophet.deployments.list().parent.customer_id
    prophet.deployments.delete(customer_id=customer_id, parent_id=parent_id)


def _env(name: str) -> str:
    """Read a required env var, exiting with a clear message if it's unset."""
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"error: environment variable {name} is required")
    return value


def _run_setup(prophet: Prophet, customer: str, handle: str) -> int:
    deployment_id = onboard_end_customer(prophet, customer, handle)
    profile_id = create_fleet_profile(prophet, f"{customer} fleet", interface_patterns=["eth*"])
    print("One-time setup complete. Export these for per-unit provisioning:")
    print(f"  export PROPHET_DEPLOYMENT_ID={deployment_id}")
    print(f"  export PROPHET_PROFILE_ID={profile_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prophet factory provisioning reference.")
    parser.add_argument("--setup", action="store_true", help="one-time: create a child deployment + fleet profile")
    parser.add_argument("--customer", help="[--setup] end-customer display name")
    parser.add_argument("--handle", help="[--setup] url-safe end-customer handle")
    parser.add_argument("--cpu-id", help="the board's hardware CPU ID")
    parser.add_argument("--serial", help="unit serial / asset tag")
    parser.add_argument("--out", default="./device", help="dir to write device files into")
    parser.add_argument("--wait", action="store_true", help="poll for enrollment after provisioning")
    args = parser.parse_args()

    prophet = Prophet(
        base_url=os.environ.get("PROPHET_BASE_URL", "https://app.prophet.io"),
        client_id=_env("PROPHET_CLIENT_ID"),
        client_secret=_env("PROPHET_CLIENT_SECRET"),
    )

    if args.setup:
        if not args.customer or not args.handle:
            parser.error("--setup requires --customer and --handle")
        return _run_setup(prophet, args.customer, args.handle)

    if not args.cpu_id or not args.serial:
        parser.error("--cpu-id and --serial are required for per-unit provisioning")

    # Deployment + profile are one-time setup (run with --setup, then export the IDs).
    deployment = _env("PROPHET_DEPLOYMENT_ID")
    profile_id = _env("PROPHET_PROFILE_ID")

    unit = provision_unit(
        prophet,
        deployment=deployment,
        cpu_id=args.cpu_id,
        serial=args.serial,
        profile_id=profile_id,
        out_dir=Path(args.out),
    )

    # Safe to print: identifiers, never the access_key secret.
    print(f"Provisioned {args.serial}")
    print(f"  machine_id: {unit.machine_id}   (store with the unit in your ops DB)")
    print(f"  device files written to: {args.out}/  (copy to the unit; yaml holds a secret)")

    if args.wait:
        print("Waiting for the unit to boot and enroll...")
        ok = wait_for_enrollment(prophet, unit.machine_id)
        print("  ENROLLED — clear for shipping" if ok else "  not enrolled yet (boot the unit with these files)")
        return 0 if ok else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
