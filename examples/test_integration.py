#!/usr/bin/env python3
"""
Integration test script for Prophet SDK.

Set these environment variables before running:
    export PROPHET_BASE_URL="https://your-api.prophet.io"
    export PROPHET_CLIENT_ID="your_client_id"
    export PROPHET_CLIENT_SECRET="your_client_secret"
    export PROPHET_INSTANCE_ID="your_instance_id"

Or edit the values below directly.
"""

import os
from prophet.sdk import Prophet, Q, HoursAgo, Now

# Configuration - set via env vars or edit directly
BASE_URL = os.getenv("PROPHET_BASE_URL", "")
CLIENT_ID = os.getenv("PROPHET_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("PROPHET_CLIENT_SECRET", "")
INSTANCE_ID = os.getenv("PROPHET_INSTANCE_ID", "")


def main():
    if not all([BASE_URL, CLIENT_ID, CLIENT_SECRET, INSTANCE_ID]):
        print("Please set the required environment variables or edit this script:")
        print("  PROPHET_BASE_URL, PROPHET_CLIENT_ID, PROPHET_CLIENT_SECRET, PROPHET_INSTANCE_ID")
        return

    print(f"Connecting to {BASE_URL}...")

    prophet = Prophet(
        base_url=BASE_URL,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
    )

    # Test 1: Health check
    print("\n--- Health Check ---")
    try:
        health = prophet.health()
        print(f"Status: {health.status}")
        print(f"Service: {health.service}")
        print(f"Version: {health.version}")
    except Exception as e:
        print(f"Health check failed: {e}")

    # Test 2: Simple flow query
    print("\n--- Flow Query (last hour, first 5 results) ---")
    try:
        count = 0
        for flow in prophet.flows(
            instances=[INSTANCE_ID],
            start=HoursAgo(1),
            end=Now(),
        ).take(5):
            count += 1
            print(f"  {flow.src.ip}:{flow.src.port} -> {flow.dst.ip}:{flow.dst.port}")
            print(f"    bytes={flow.bytes}, app={flow.app_name}")
        print(f"Retrieved {count} flows")
    except Exception as e:
        print(f"Flow query failed: {e}")

    # Test 3: Query with filter
    print("\n--- Filtered Query (port 443, last hour) ---")
    try:
        query = Q("dst.port").eq(443)
        print(f"PQL: {query.build()}")

        page = prophet.flows(
            instances=[INSTANCE_ID],
            query=query,
            start=HoursAgo(1),
            end=Now(),
            size=10,
        ).first()

        print(f"Found: {page.found} total matches")
        print(f"Returned: {page.returned} in this page")
        print(f"Query took: {page.took:.3f}s")

        for flow in page.flows[:3]:
            print(f"  {flow.src.ip} -> {flow.dst.ip}:{flow.dst.port}")
    except Exception as e:
        print(f"Filtered query failed: {e}")

    # Test 4: Pagination
    print("\n--- Pagination Test ---")
    try:
        iterator = prophet.flows(
            instances=[INSTANCE_ID],
            start=HoursAgo(1),
            size=10,  # Small page size
        )

        # Get first page
        page1 = iterator.first()
        print(f"Page 1: {page1.returned} flows, has_more={page1.has_more}")

        if page1.has_more:
            page2 = iterator.next_page()
            print(f"Page 2: {page2.returned} flows, has_more={page2.has_more}")
    except Exception as e:
        print(f"Pagination test failed: {e}")

    print("\n--- Done ---")


if __name__ == "__main__":
    main()
