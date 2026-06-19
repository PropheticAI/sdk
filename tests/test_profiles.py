"""Tests for the profiles API."""

from __future__ import annotations

import pytest
import responses

from prophet.sdk import ValidationError
from prophet.sdk.profiles import lightweight_packet_services
from tests.conftest import BASE_URL, register_token

PROFILES_URL = f"{BASE_URL}/rest/profiles/1.0"


def test_lightweight_packet_services_shape():
    svc = lightweight_packet_services(interface_patterns=["eth*"])
    assert svc["packet"]["enabled"] is True
    assert svc["packet"]["lightweight"] is True
    assert svc["packet"]["interface_patterns"] == ["eth*"]
    assert svc["packet"]["num_workers"] == 1


def test_create_requires_name(prophet):
    with pytest.raises(ValidationError):
        prophet.profiles.create(name="")


@responses.activate
def test_create_returns_profile(prophet):
    register_token()
    responses.add(
        responses.POST,
        PROFILES_URL,
        json={"status": "success", "profile": {
            "profile_id": "prof-1", "customer_id": "parent-1", "name": "Fleet A",
            "update_channel": "stable",
        }},
        status=201,
    )
    profile = prophet.profiles.create(name="Fleet A", services=lightweight_packet_services())
    assert profile.profile_id == "prof-1"
    assert profile.name == "Fleet A"


@responses.activate
def test_list_profiles(prophet):
    register_token()
    responses.add(
        responses.GET,
        PROFILES_URL,
        json={"profiles": [{"profile_id": "prof-1", "customer_id": "parent-1", "name": "A"}]},
        status=200,
    )
    profiles = prophet.profiles.list()
    assert len(profiles) == 1 and profiles[0].profile_id == "prof-1"


@responses.activate
def test_delete_profile_returns_none(prophet):
    register_token()
    responses.add(
        responses.DELETE, f"{PROFILES_URL}/prof-1", json={"status": "success"}, status=200
    )
    assert prophet.profiles.delete("prof-1") is None
