"""Tests for the deployments API (flat return types)."""

from __future__ import annotations

import pytest
import responses

from prophet.sdk import Deployment, ValidationError
from tests.conftest import BASE_URL, register_token

DEPLOYMENTS_URL = f"{BASE_URL}/rest/deployments/1.0"


@responses.activate
def test_list_returns_list_of_deployments(prophet):
    register_token()
    responses.add(
        responses.GET,
        DEPLOYMENTS_URL,
        json={
            "parent": {"customer_id": "test-parent", "name": "Parent", "handle": "parent"},
            "deployments": [
                {"customer_id": "child-1", "name": "Child One", "parent": "test-parent"},
                {"customer_id": "child-2", "name": "Child Two", "parent": "test-parent"},
            ],
            "count": 2,
        },
        status=200,
    )
    result = prophet.deployments.list()
    assert isinstance(result, list)
    assert all(isinstance(d, Deployment) for d in result)
    assert [d.customer_id for d in result] == ["child-1", "child-2"]


@responses.activate
def test_create_returns_deployment_and_defaults_parent(prophet):
    register_token(aud="test-parent")
    responses.add(
        responses.POST,
        DEPLOYMENTS_URL,
        json={"deployment": {
            "customer": {"customer_id": "test-parent-x1", "name": "ACME", "handle": "acme",
                         "type": "child", "parent": "test-parent", "org_code": "org_abc"},
            "org": {"code": "org_abc", "name": "ACME", "handle": "acme"},
        }},
        status=201,
    )
    child = prophet.deployments.create(name="ACME", handle="acme")
    assert isinstance(child, Deployment)
    assert child.customer_id == "test-parent-x1"
    assert child.org_code == "org_abc"  # extra field captured
    # parent_id defaulted to prophet.customer_id (the JWT aud)
    sent = responses.calls[-1].request.body
    assert b'"parent_id": "test-parent"' in sent


@responses.activate
def test_delete_returns_none(prophet):
    register_token(aud="test-parent")
    responses.add(responses.DELETE, DEPLOYMENTS_URL, json={"status": "success"}, status=200)
    assert prophet.deployments.delete("child-1") is None


@responses.activate
def test_get_finds_by_customer_id(prophet):
    register_token()
    responses.add(
        responses.GET,
        DEPLOYMENTS_URL,
        json={"deployments": [{"customer_id": "child-1", "name": "C1"}], "count": 1},
        status=200,
    )
    assert prophet.deployments.get("child-1").customer_id == "child-1"
    # second list call for the miss
    responses.add(
        responses.GET,
        DEPLOYMENTS_URL,
        json={"deployments": [{"customer_id": "child-1", "name": "C1"}], "count": 1},
        status=200,
    )
    assert prophet.deployments.get("nope") is None


def test_create_requires_name_and_handle(prophet):
    with pytest.raises(ValidationError):
        prophet.deployments.create(name="", handle="x")
    with pytest.raises(ValidationError):
        prophet.deployments.create(name="x", handle="")
