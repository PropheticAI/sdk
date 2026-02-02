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

# Initialize client
prophet = Prophet(
    base_url="https://app.prophet.io",
    client_id="your_client_id",
    client_secret="your_client_secret"
)

# Iterate over flows - pagination is automatic
for flow in prophet.flows(
    instances=["instance-1"],
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

## Context Manager

```python
with Prophet(base_url, client_id, client_secret) as prophet:
    for flow in prophet.flows(...):
        process(flow)
# Session automatically closed
```

## License

MIT
