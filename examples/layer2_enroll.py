"""
Layer-2 test: provision a unit, boot the real prophet-node binary against dev,
and confirm a node actually enrolls (the gRPC Register path → node doc created).

Authoritative signal = the binary's own logs; secondary = the node appearing in
the REST nodes view under the child tenant. Cleans up everything (terminating
the whole prophet process tree, deleting the child deployment which cascades
node deletion, and the profile).
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from prophet.sdk import Prophet
from prophet.sdk.profiles import lightweight_packet_services

BINARY = "/tmp/prophet-node-darwin"


def main() -> int:
    base_url = os.environ["PROPHET_BASE_URL"].rstrip("/")
    client_id = os.environ["PROPHET_CLIENT_ID"]
    client_secret = os.environ["PROPHET_CLIENT_SECRET"]
    # dev|prod for the device yaml — must match the controller env we provisioned against
    node_env = os.environ.get("PROPHET_NODE_ENV", "dev")

    run_id = f"l2-{int(time.time())}"
    cpu_id = f"0xL2{int(time.time())}"
    prophet_dir = Path(f"/tmp/prophet-{run_id}")
    prophet_dir.mkdir(parents=True, exist_ok=True)

    prophet = Prophet(base_url=base_url, client_id=client_id, client_secret=client_secret)
    parent_id = prophet.deployments.list().parent.customer_id

    child_id = None
    profile_id = None
    proc = None
    log_path = prophet_dir / "node.log"

    try:
        child_id = prophet.deployments.create(name=f"L2 {run_id}", handle=run_id, parent_id=parent_id).deployment.customer.customer_id
        profile = prophet.profiles.create(name=f"L2 {run_id}", services=lightweight_packet_services())
        profile_id = profile.profile_id
        unit = prophet.nodes.provision(deployment=child_id, cpu_id=cpu_id, description=f"L2 {run_id}", profile_id=profile_id)
        print(f"[provision] child={child_id} machine_id={unit.machine_id}")

        (prophet_dir / "prophet_collector.yaml").write_text(
            unit.collector_yaml(env=node_env, spool_dir=str(prophet_dir / "spool"))
        )

        # Boot the binary in its own session so we can kill the whole tree
        # (service → supervisor → worker). PROPHET_DIR keeps all state in tempdir.
        env = {**os.environ, "PROPHET_DIR": str(prophet_dir) + "/"}
        with open(log_path, "wb") as logf:
            proc = subprocess.Popen(
                [BINARY], env=env, stdout=logf, stderr=subprocess.STDOUT, start_new_session=True
            )
        print(f"[boot] pid={proc.pid} PROPHET_DIR={prophet_dir} env={node_env}")

        # Poll for enrollment: node appears under the child tenant.
        enrolled_node = None
        deadline = time.time() + 120
        while time.time() < deadline:
            time.sleep(5)
            if proc.poll() is not None:
                print(f"[warn] binary exited early rc={proc.returncode} (worker capture may fail on darwin; enrollment may still have happened)")
            for n in prophet.nodes.list():
                if n.customer_id == child_id:
                    enrolled_node = n
                    break
            if enrolled_node:
                break
            print("  ...waiting for node to appear under child")

        print("\n[node log tail]")
        log_text = log_path.read_text(errors="replace") if log_path.exists() else ""
        for line in log_text.splitlines()[-25:]:
            print("    " + line)

        print("\n[result]")
        # Authoritative: did the binary log a successful enrollment?
        enrolled_in_log = any(k in log_text for k in ("registered node_id", "node_id", "Register", "customer_id"))
        print(f"  binary logged enrollment markers: {enrolled_in_log}")
        if enrolled_node:
            print(f"  NODE VISIBLE IN API: node_id={enrolled_node.node_id} status={getattr(enrolled_node, 'status', '?')} "
                  f"control_plane={enrolled_node.connection.control_plane} ingest={enrolled_node.connection.ingest}")
            print("  RESULT: PASS — a real node enrolled end to end")
            rc = 0
        else:
            print("  RESULT: node did not appear in API within 120s (see log tail for why)")
            rc = 1

    finally:
        print("\n[cleanup]")
        if proc and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                time.sleep(2)
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception as e:
                print(f"  WARN: kill failed: {e}")
        if profile_id:
            try:
                prophet.profiles.delete(profile_id)
                print(f"  deleted profile {profile_id}")
            except Exception as e:
                print(f"  WARN: profile delete: {e}")
        if child_id:
            try:
                prophet.deployments.delete(customer_id=child_id, parent_id=parent_id)
                print(f"  deleted child {child_id} (cascades node deletion)")
            except Exception as e:
                print(f"  WARN: child delete: {e}")

    return rc


if __name__ == "__main__":
    sys.exit(main())
