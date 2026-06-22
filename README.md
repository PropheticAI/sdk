# Prophet SDK

Python SDK for Prophet's API.

## Installation

```bash
pip install prophet-sdk
```

Or install from source:

```bash
pip install -e .
```

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

## Context Manager

```python
with Prophet(client_id="your_client_id", client_secret="your_client_secret") as prophet:
    for flow in prophet.flows(...):
        process(flow)
# Session automatically closed
```

## License

MIT
