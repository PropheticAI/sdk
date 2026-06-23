# Prophet SDK

Python SDK for the Prophet API.

- `prophet.flows` — query flow records (auto-paginating)
- `prophet.deployments` — manage sub-deployments (MSP child tenants)
- `prophet.nodes` — provision and inspect nodes
- `prophet.profiles` — node capture-config templates
- `prophet.collector` — download the prophet-node binary
- `prophet.factory` — end-to-end unit-provisioning workflow

## Installation

```bash
pip install "git+https://github.com/PropheticAI/sdk.git@v0.4.0"
```

Public repo — no credentials needed to install. From a local clone: `pip install -e .`.

## Authentication

To use the Prophet SDK, you need API credentials. Create an account at:

https://prophetic.ai/

After signing up, you'll receive a `client_id` and `client_secret` for API access.

## Quick Start

```python
from prophet.sdk import Prophet, Q, HoursAgo, Now

# Initialize client (base_url defaults to production, https://app.prophet.io)
prophet = Prophet(
    client_id="your_client_id",
    client_secret="your_client_secret",
)

# Iterate over flows - pagination is automatic
for flow in prophet.flows(
    instance="instance-1",
    query=Q("dst.port").eq(443),
    start=HoursAgo(24),
    end=Now(),
):
    print(f"{flow.src.ip}:{flow.src.port} -> {flow.dst.ip}:{flow.dst.port}")
    print(f"  bytes: {flow.bytes}, app: {flow.app_name}")
```

## Query Builder

Build PQL queries fluently:

```python
from prophet.sdk import Q

# Simple conditions
Q("dst.port").eq(443)
Q("bytes").gt(1000)
Q("src.ip").wildcard("192.168.*")
Q("protocol").in_(["tcp", "udp"])

# Compound queries
query = Q("dst.port").eq(443).and_("bytes").gt(1000)

# Grouped queries
inner = Q("protocol").eq("tcp").or_("protocol").eq("udp")
query = Q.group(inner).and_("dst.port").eq(443)
# Result: (protocol eq tcp or protocol eq udp) and dst.port eq 443

# Raw PQL string
query = Q.raw("dst.ip eq 10.90.8.53 and dst.port eq 53")
```

## Time Filters

```python
from prophet.sdk import Now, HoursAgo, DaysAgo, MinutesAgo, At
from datetime import datetime

# Relative times
start=HoursAgo(24)
start=DaysAgo(7)
start=MinutesAgo(30)

# Absolute time
start=At("2025-01-15T00:00:00Z")
start=At(datetime(2025, 1, 15))

# Current time
end=Now()
```

## Iterator Controls

```python
# Iterate all (auto-pagination)
for flow in prophet.flows(...):
    process(flow)

# Limit total results
for flow in prophet.flows(...).take(1000):
    process(flow)

# Get first page only
page = prophet.flows(...).first()
print(f"Found {page.found} total matches")

# Collect into list
flows = prophet.flows(...).take(100).collect()

# Manual pagination
iterator = prophet.flows(...)
while True:
    page = iterator.next_page()
    if page is None:
        break
    for flow in page.flows:
        process(flow)
```

## Flow Object

Access flow data with dot notation:

```python
# Endpoint access (both styles work)
flow.src.ip          # "192.168.1.100"
flow.src_ip          # "192.168.1.100" (shortcut)
flow.src.port        # 54321
flow.dst.ip          # "10.90.8.53"
flow.dst.port        # 53

# Transport and protocol
flow.transport.proto # "UDP"
flow.protocol        # "UDP" (shortcut)

# Metrics
flow.bytes           # 512 (from metric.total_bytes or stats)
flow.packets         # 6

# Metadata
flow.app_name        # "DNS"
flow.instance_id     # "your-instance-id"
flow.timestamp       # 1706000000000 (Unix ms)
flow.timestamp_dt    # datetime object

# Deep access to stats
flow.stats.rate.bps.total      # bits per second
flow.stats.volume.bytes.total  # total bytes
flow.meta.tags                 # ["tag1", "tag2"]
```

## Deployments API

Manage sub-deployments (child tenants) for MSP parent accounts.

`parent_id` defaults to the authenticated tenant (`prophet.customer_id`), so a
parent MSP rarely needs to pass it.

### List Sub-Deployments

```python
# Returns list[Deployment]
for deployment in prophet.deployments.list():
    print(f"  - {deployment.name} ({deployment.customer_id})")
```

### Create a Sub-Deployment

```python
# Returns the created Deployment
child = prophet.deployments.create(name="ACME Corp", handle="acme_corp")
print(f"Created: {child.customer_id}")
```

### Delete a Sub-Deployment

```python
# Returns None. Cascades deletion of the deployment's nodes and credentials.
prophet.deployments.delete("sub-deployment-123")
```

### Get a Specific Deployment

```python
deployment = prophet.deployments.get("sub-deployment-123")
if deployment:
    print(f"Found: {deployment.name}")
```

### Deployment Object

```python
deployment.customer_id  # "acme-a1234b567"
deployment.name         # "ACME Corp"
deployment.handle       # "acme_corp"
deployment.type         # "child"
deployment.parent       # "parent-123"
deployment.created_at   # "2026-02-04T16:00:00Z"
```

## Nodes API

Provision units and inspect nodes. (For the full build-a-unit workflow, see Factory below.)

```python
# Provision a unit -> per-unit access_key + deterministic machine_id
unit = prophet.nodes.provision(
    deployment="<child-customer-id>", cpu_id="0x1122334455", profile_id="<profile-uuid>",
)
unit.access_key   # store in your ops DB (shown once)
unit.machine_id   # deterministic from cpu_id -> join key

# Inspect
nodes = prophet.nodes.list()              # list[Node] (incl. children for a parent MSP)
node = prophet.nodes.get("<node_id>")     # or None
node = prophet.nodes.find_by_machine_id(unit.machine_id)
node.is_enrolled                          # True = active + control-plane connected
```

## Profiles (capture config)

A profile is a reusable capture-config template referenced by units. Build it
with the typed `ProfileServices` — only the fields you set are sent; the server
fills the rest with defaults, and a misspelled field raises immediately (rather
than silently doing nothing).

```python
from prophet.sdk import ProfileServices, PacketServices

prof = prophet.profiles.create(
    name="TerraLynk fleet",
    services=ProfileServices(
        packet=PacketServices(enabled=True, lightweight=True, interface_patterns=["eth*"]),
    ),
)

# Or the constrained-edge shortcut (lightweight, pinned iface, 1 worker, DPI off):
from prophet.sdk.profiles import lightweight_packet_services
prophet.profiles.create(name="Fleet", services=lightweight_packet_services(["eth*"]))
```

Available options (all optional):

- **packet** — `enabled`, `interface_patterns` (globs, matched per-node), `inspection`
  (DPI; TCP reassembly + TLS/DNS — memory-heavy), `payload`, `lightweight`, `ephemeral`,
  `afpacket`, `gre`, `process_ids`, `num_workers`, `num_spoolers`, and buffer/spool sizing
  (`packet_buffer_length`, `afpacket_block_size`, `afpacket_num_blocks`,
  `packet_buffer_timeout_ms`, `max_spooled_files`, `max_spooled_file_size`, `ingest_stream_interval`).
- **netflow** — `enabled`, `port`.
- **suricata_logs** / **suricata_ids** — `enabled`.
- **host_logs** — `enabled` (off by default), `excluded_sources` — a list of sources to
  **exclude**; everything else for the node's OS is collected.

A raw `dict` is also accepted as an escape hatch (`services={"netflow": {...}}`), but the
typed form is recommended — it validates field names.

## Factory (provisioning workflow)

`prophet.factory` is a workflow layer (not an API wrapper): one call provisions a
unit, fetches its binary, and writes a ready-to-flash bundle. You supply domain
facts; paths/perms/args/env are computed.

```python
inst = prophet.factory.build(
    deployment_id="meshcomm-x1234y567",   # child deployment (end customer)
    cpu_id="0x1122334455667788",          # board CPU ID -> deterministic machine_id
    profile_id="<profile-uuid>",          # fleet capture profile
    serial="SN-0042",
    arch="arm7",
    out_dir="./installers/SN-0042",
)

inst.access_key   # per-unit secret (shown once) -> store in your ops DB
inst.machine_id   # deterministic from cpu_id -> ops DB join key
inst.bundle_dir   # bin/prophet + prophet_collector.yaml + prophet-node.service
                  # + install.sh + manifest.json  -> copy to the unit, run install.sh
```

Your flashing pipeline copies `bundle_dir` to the unit and runs `install.sh`
(places files, enables the service). Then gate on enrollment:

```python
node = prophet.nodes.find_by_machine_id(inst.machine_id)
ship_ok = node is not None and node.is_enrolled
```

## Collector Binary

Download the prophet-node binary (latest stable per platform/channel) — no GitHub
access needed; the controller proxies the signed release.

```python
# Fetch + unpack the latest stable ARM7 binary, ready to flash
binary = prophet.collector.download(arch="arm7", extract=True, dest="./dist")
# binary -> ./dist/prophet (executable)

# Other architectures / channels
prophet.collector.download(os="linux", arch="amd64")          # tarball, current dir
prophet.collector.download(arch="arm64", channel="dev")

# Just the (stable, always-latest) URL for an install script
url = prophet.collector.download_url(arch="arm7")
```

Downloads are cached on disk by the release's versioned filename, so flashing a
batch of the same SKU doesn't re-transfer the binary; a new release is fetched
automatically. Override the location with `$PROPHET_SDK_CACHE_DIR`, or pass
`cache=False` to force a fresh fetch.

## Context Manager

```python
with Prophet(client_id="your_client_id", client_secret="your_client_secret") as prophet:
    for flow in prophet.flows(...):
        process(flow)
# Session automatically closed
```

## License

MIT
