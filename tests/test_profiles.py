"""Tests for the profiles API."""

from __future__ import annotations

import pydantic
import pytest
import responses

from prophet.sdk import PacketServices, ProfileServices, ValidationError
from prophet.sdk.profiles import lightweight_packet_services
from tests.conftest import BASE_URL, register_token

PROFILES_URL = f"{BASE_URL}/rest/profiles/1.0"


def test_lightweight_packet_services():
    svc = lightweight_packet_services(interface_patterns=["eth*"])
    assert isinstance(svc, ProfileServices)
    p = svc.packet
    assert p.enabled is True and p.lightweight is True
    assert p.interface_patterns == ["eth*"] and p.num_workers == 1
    assert p.inspection is False and p.payload is False  # DPI off for low footprint


def test_profile_services_payload_omits_unset():
    # Only set fields are serialized — server defaults fill the rest.
    payload = ProfileServices(packet=PacketServices(enabled=True, lightweight=True)).to_payload()
    assert payload == {"packet": {"enabled": True, "lightweight": True}}


def test_unknown_packet_field_rejected():
    # Typo'd field raises at construction instead of silently no-op'ing server-side.
    with pytest.raises(pydantic.ValidationError):
        PacketServices(interfaces=["eth0"])  # should be interface_patterns


def test_unknown_top_level_service_rejected():
    with pytest.raises(pydantic.ValidationError):
        ProfileServices(packets={})  # should be 'packet'


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
    # typed services serialized to the request body, unset fields omitted
    import json
    sent = json.loads(responses.calls[-1].request.body)
    assert sent["services"]["packet"]["inspection"] is False
    assert "afpacket" not in sent["services"]["packet"]  # unset -> omitted (server default)


@responses.activate
def test_create_accepts_raw_dict(prophet):
    register_token()
    responses.add(
        responses.POST, PROFILES_URL,
        json={"status": "success", "profile": {
            "profile_id": "p2", "customer_id": "c", "name": "B",
        }},
        status=201,
    )
    # escape hatch: a raw dict is passed through unchanged
    prophet.profiles.create(name="B", services={"netflow": {"enabled": True, "port": 2055}})
    import json
    sent = json.loads(responses.calls[-1].request.body)
    assert sent["services"] == {"netflow": {"enabled": True, "port": 2055}}


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
