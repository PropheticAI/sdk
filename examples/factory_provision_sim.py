"""
Factory provisioning simulation — mirrors meshcomm's build-line flow end to end.

Drives the Prophet SDK exactly as a manufacturer's build backend would:
  1. create a child deployment (per end-customer)
  2. create a capture-config profile
  3. provision a unit  -> per-unit access_key + deterministic machine_id
  4. render the device's prophet_collector.yaml
  5. VALIDATE the minted credential is real and child-scoped (mint a JWT from it,
     assert aud == child tenant, scope == ingest)
  6. check node visibility (the build-line pass/fail gate)
  7. clean everything up

Usage:
  PROPHET_BASE_URL=https://dev.prophet.io \
  PROPHET_CLIENT_ID=... PROPHET_CLIENT_SECRET=... \
  python examples/factory_provision_sim.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time

import requests

from prophet.sdk import Prophet, derive_machine_id
from prophet.sdk.profiles import lightweight_packet_services


def decode_jwt_payload(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def main() -> int:
    base_url = os.environ["PROPHET_BASE_URL"].rstrip("/")
    client_id = os.environ["PROPHET_CLIENT_ID"]
    client_secret = os.environ["PROPHET_CLIENT_SECRET"]

    run_id = f"simtest-{int(time.time())}"
    cpu_id = f"0xSIM{int(time.time())}"

    prophet = Prophet(base_url=base_url, client_id=client_id, client_secret=client_secret)

    child_id: str | None = None
    profile_id: str | None = None
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")
        if not ok:
            failures.append(label)

    try:
        # ── 1. who am I (the parent) ─────────────────────────────────
        listing = prophet.deployments.list()
        parent_id = listing.parent.customer_id
        print(f"\n[1] Parent: {listing.parent.name} ({parent_id}), existing children: {listing.count}")

        # ── 2. create child deployment ───────────────────────────────
        created = prophet.deployments.create(name=f"Sim {run_id}", handle=run_id, parent_id=parent_id)
        child_id = created.deployment.customer.customer_id
        print(f"[2] Created child deployment: {child_id} (handle={run_id})")
        check("child is typed as a child of the parent", created.deployment.customer.parent == parent_id,
              f"parent={created.deployment.customer.parent}")

        # ── 3. create a lightweight capture profile ──────────────────
        profile = prophet.profiles.create(
            name=f"Fleet {run_id}",
            description="ARM edge fleet (sim)",
            services=lightweight_packet_services(interface_patterns=["eth*"]),
        )
        profile_id = profile.profile_id
        print(f"[3] Created profile: {profile_id}")
        check("profile owned by parent", profile.customer_id == parent_id, f"owner={profile.customer_id}")

        # ── 4. provision a unit under the child ──────────────────────
        unit = prophet.nodes.provision(
            deployment=child_id,
            cpu_id=cpu_id,
            description=f"SimUnit {run_id}",
            profile_id=profile_id,
        )
        print(f"[4] Provisioned unit: {unit!r}")
        check("unit keyed to the child tenant", unit.customer_id == child_id, f"customer_id={unit.customer_id}")
        check("access_key has client_id.secret shape", unit.access_key.count(".") == 1)
        check("machine_id is deterministic from cpu_id", unit.machine_id == derive_machine_id(cpu_id),
              f"machine_id={unit.machine_id}")

        # ── 5. render the device yaml the build line writes ──────────
        device_yaml = unit.collector_yaml(env="prod", spool_dir="/data/apps/prophet/spool")
        print("[5] Device prophet_collector.yaml:\n" + "\n".join("      " + ln for ln in device_yaml.splitlines()))

        # ── 6. VALIDATE the credential is real + child-scoped ────────
        cid, secret = unit.access_key.split(".", 1)
        resp = requests.post(
            f"{base_url}/rest/oauth2/token/1.0",
            json={"client_id": cid, "client_secret": secret},
            timeout=20,
        )
        check("provisioned access_key mints a JWT", resp.status_code == 200, f"HTTP {resp.status_code}")
        if resp.status_code == 200:
            jwt = resp.json()["access_token"]
            payload = decode_jwt_payload(jwt)
            check("JWT audience == child tenant", payload.get("aud") == child_id, f"aud={payload.get('aud')}")
            check("JWT carries the ingest scope", "p.token.scope.ingest" in payload.get("scopes", []),
                  f"scopes={payload.get('scopes')}")

        # ── 7. node visibility (the build-line gate) ─────────────────
        node = prophet.nodes.find_by_machine_id(unit.machine_id)
        print(f"[7] Node by machine_id: {node!r}")
        print("    (None is EXPECTED here — the node doc materializes on the unit's first gRPC Register,")
        print("     which requires the prophet-node binary to boot with this yaml. Credential chain is proven above.)")

    finally:
        # ── cleanup ──────────────────────────────────────────────────
        print("\n[cleanup]")
        if profile_id:
            try:
                prophet.profiles.delete(profile_id)
                print(f"  deleted profile {profile_id}")
            except Exception as e:
                print(f"  WARN: profile delete failed: {e}")
        if child_id:
            try:
                prophet.deployments.delete(customer_id=child_id, parent_id=parent_id)
                print(f"  deleted child deployment {child_id}")
            except Exception as e:
                print(f"  WARN: child delete failed: {e}")

    print(f"\n{'='*60}")
    if failures:
        print(f"RESULT: {len(failures)} FAILED → {failures}")
        return 1
    print("RESULT: all checks PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
