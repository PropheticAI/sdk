"""Tests for the nodes API: provisioning, listing, and the build-line gate."""

from __future__ import annotations

import pytest
import responses

from prophet.sdk import ValidationError, derive_machine_id
from tests.conftest import BASE_URL, register_token

PROVISION_URL = f"{BASE_URL}/rest/nodes/provision/1.0"
NODES_URL = f"{BASE_URL}/rest/nodes/1.0"


def test_derive_machine_id_is_deterministic():
    assert derive_machine_id("0xCAFE") == derive_machine_id("0xCAFE")
    assert derive_machine_id("0xCAFE") != derive_machine_id("0xBEEF")


def test_derive_machine_id_requires_cpu_id():
    with pytest.raises(ValidationError):
        derive_machine_id("")


def test_provision_requires_deployment(prophet):
    with pytest.raises(ValidationError):
        prophet.nodes.provision(deployment="", cpu_id="0x1")


def test_provision_requires_cpu_or_machine_id(prophet):
    with pytest.raises(ValidationError):
        prophet.nodes.provision(deployment="child-1")


@responses.activate
def test_provision_returns_unit(prophet):
    register_token()
    responses.add(
        responses.POST,
        PROVISION_URL,
        json={
            "status": "success",
            "access_key": "clientid.secretpart",
            "customer_id": "child-1",
            "machine_id": derive_machine_id("0xABC"),
            "profile_id": "prof-1",
        },
        status=201,
    )
    unit = prophet.nodes.provision(deployment="child-1", cpu_id="0xABC", profile_id="prof-1")
    assert unit.customer_id == "child-1"
    assert unit.access_key == "clientid.secretpart"
    assert unit.machine_id == derive_machine_id("0xABC")
    # Secret never leaks into repr.
    assert "secretpart" not in repr(unit)
    # Rendered device config carries the key + spool dir.
    yaml = unit.collector_yaml(env="prod", spool_dir="/data/spool")
    assert 'access_key: "clientid.secretpart"' in yaml
    assert "spool_dir: /data/spool" in yaml


@responses.activate
def test_list_nodes(prophet):
    register_token()
    responses.add(
        responses.GET,
        NODES_URL,
        json={"nodes": [{"node_id": "n1", "customer_id": "child-1", "status": "active"}]},
        status=200,
    )
    nodes = prophet.nodes.list()
    assert len(nodes) == 1
    assert nodes[0].node_id == "n1"


@responses.activate
def test_get_node_404_returns_none(prophet):
    register_token()
    responses.add(responses.GET, f"{NODES_URL}/missing", json={"error": "not found"}, status=404)
    assert prophet.nodes.get("missing") is None


@responses.activate
def test_find_by_machine_id_and_is_enrolled(prophet):
    register_token()
    mid = derive_machine_id("0xABC")
    responses.add(
        responses.GET,
        NODES_URL,
        json={"nodes": [{
            "node_id": "n1", "machine_id": mid, "customer_id": "child-1",
            "status": "active", "connection": {"control_plane": True, "ingest": True},
        }]},
        status=200,
    )
    node = prophet.nodes.find_by_machine_id(mid)
    assert node is not None and node.node_id == "n1"
    assert node.is_active and node.is_enrolled


@responses.activate
def test_pending_node_not_enrolled(prophet):
    register_token()
    mid = derive_machine_id("0xDEF")
    responses.add(
        responses.GET,
        NODES_URL,
        json={"nodes": [{
            "node_id": "n2", "machine_id": mid, "customer_id": "child-1",
            "status": "pending_approval", "connection": {"control_plane": True, "ingest": False},
        }]},
        status=200,
    )
    node = prophet.nodes.find_by_machine_id(mid)
    assert node is not None and not node.is_enrolled
