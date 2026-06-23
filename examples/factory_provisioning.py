"""
Prophet factory provisioning — reference integration for a manufacturing line.

A manufacturer ships units pre-enrolled in Prophet with no human approval. The
SDK does the heavy lifting: `prophet.factory.build()` provisions a unit, fetches
its binary, and writes a ready-to-flash bundle (binary + config + systemd unit +
install.sh). You supply domain facts (end customer, CPU ID, SKU profile, serial)
— never device paths/args/env.

One-time per end customer / hardware SKU (prints the two IDs to reuse per unit):

    PROPHET_CLIENT_ID=... PROPHET_CLIENT_SECRET=... \
    python examples/factory_provisioning.py --setup --customer "Acme Corp" --handle acme

Per unit, on the build line:

    PROPHET_CLIENT_ID=... PROPHET_CLIENT_SECRET=... \
    PROPHET_DEPLOYMENT_ID=<child-id> PROPHET_PROFILE_ID=<profile-id> \
    python examples/factory_provisioning.py --cpu-id 0x1122334455667788 --serial SN-0042 --wait

Then your flashing pipeline copies the bundle to the unit and runs install.sh.
"""

from __future__ import annotations

import argparse
import os
import time

from prophet.sdk import Prophet
from prophet.sdk.profiles import lightweight_packet_services


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"error: environment variable {name} is required")
    return value


# ── One-time setup ──────────────────────────────────────────────────────────
def setup(prophet: Prophet, customer: str, handle: str) -> int:
    """Create a child deployment (per end customer) + a fleet profile (per SKU)."""
    deployment_id = prophet.deployments.create(name=customer, handle=handle).customer_id
    profile_id = prophet.profiles.create(
        name=f"{customer} fleet",
        services=lightweight_packet_services(interface_patterns=["eth*"]),
    ).profile_id
    print("One-time setup complete. Export these for per-unit provisioning:")
    print(f"  export PROPHET_DEPLOYMENT_ID={deployment_id}")
    print(f"  export PROPHET_PROFILE_ID={profile_id}")
    return 0


# ── Per unit ──────────────────────────────────────────────────────────────--
def provision(prophet: Prophet, *, deployment_id: str, profile_id: str,
              cpu_id: str, serial: str, out_dir: str, wait: bool) -> int:
    """Build a ready-to-flash install bundle for one unit."""
    inst = prophet.factory.build(
        deployment_id=deployment_id,
        cpu_id=cpu_id,
        profile_id=profile_id,
        serial=serial,
        arch="arm7",
        out_dir=out_dir,
    )
    # Safe to print: identifiers, never the access_key secret.
    print(f"Provisioned {serial}")
    print(f"  machine_id: {inst.machine_id}   (store with the unit in your ops DB)")
    print(f"  bundle:     {inst.bundle_dir}/  (copy to the unit; run install.sh)")

    if wait:
        print("Waiting for the unit to boot and enroll...")
        deadline = time.time() + 180
        while time.time() < deadline:
            node = prophet.nodes.find_by_machine_id(inst.machine_id)
            if node and node.is_enrolled:
                print("  ENROLLED — clear for shipping")
                return 0
            time.sleep(5)
        print("  not enrolled yet (boot the unit with this bundle)")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prophet factory provisioning reference.")
    parser.add_argument("--setup", action="store_true", help="one-time: create a child deployment + fleet profile")
    parser.add_argument("--customer", help="[--setup] end-customer display name")
    parser.add_argument("--handle", help="[--setup] url-safe end-customer handle")
    parser.add_argument("--cpu-id", help="the board's hardware CPU ID")
    parser.add_argument("--serial", help="unit serial / asset tag")
    parser.add_argument("--out", help="dir to write the bundle into (default ./<serial>)")
    parser.add_argument("--wait", action="store_true", help="poll for enrollment after building")
    args = parser.parse_args()

    prophet = Prophet(
        client_id=_env("PROPHET_CLIENT_ID"),
        client_secret=_env("PROPHET_CLIENT_SECRET"),
        base_url=os.environ.get("PROPHET_BASE_URL", Prophet.DEFAULT_BASE_URL),
    )

    if args.setup:
        if not args.customer or not args.handle:
            parser.error("--setup requires --customer and --handle")
        return setup(prophet, args.customer, args.handle)

    if not args.cpu_id or not args.serial:
        parser.error("--cpu-id and --serial are required for per-unit provisioning")

    return provision(
        prophet,
        deployment_id=_env("PROPHET_DEPLOYMENT_ID"),
        profile_id=_env("PROPHET_PROFILE_ID"),
        cpu_id=args.cpu_id,
        serial=args.serial,
        out_dir=args.out or f"./{args.serial}",
        wait=args.wait,
    )


if __name__ == "__main__":
    raise SystemExit(main())
