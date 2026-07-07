"""Tests for the Explore ▸ Egress API — cadence, against the engine's real shape."""

from __future__ import annotations

import json

import pytest
import responses

from prophet.sdk import Beacon, Cadence, CdfPoint, ValidationError
from tests.conftest import BASE_URL, register_token

CADENCE_URL = f"{BASE_URL}/rest/explore/1.0/egress/organizations/google/cadence"

# Mirrors the traffic.egress `cadence` op output: `_ok()` envelope (status /
# results_for / timestamp) + gap-CDF rhythm keys + stats keyed by dotted field
# path (run_stats returns {field: value}) + beacon facts + readout.
_CADENCE = {
    "status": "success",
    "results_for": ["sentinel-910724", "sentinel-284391"],
    "timestamp": "2026-07-06T21:14:09.482913+00:00",
    "cdf": [
        {"gap_secs": 0.9182, "fraction": 0.01},
        {"gap_secs": 29.8811, "fraction": 0.05},
        {"gap_secs": 29.9973, "fraction": 0.25},
        {"gap_secs": 30.0044, "fraction": 0.5},
        {"gap_secs": 30.1102, "fraction": 0.75},
        {"gap_secs": 118.4471, "fraction": 0.9},
        {"gap_secs": 1743.2946, "fraction": 0.99},
    ],
    "dominant_intervals": [
        {"gap_secs": 30.0044, "fraction": 0.7},
        {"gap_secs": 118.4471, "fraction": 0.15},
    ],
    "steppedness": 0.7,
    "median_gap_secs": 30.0044,
    "stats": {
        "stats.timing.inter_arrival_secs.regularity": 0.4183,
        "stats.timing.inter_arrival_secs.mean_gap": 47.3312,
        "stats.timing.inter_arrival_secs.burstiness": -0.3121,
    },
    "beacon": {"flows": 1284, "sources": 3, "interval_ms": 30011.4},
    "readout": (
        "machine-steady, sessions beat 70% at ~30s + 15% at ~2m, "
        "1284 beacon-like flows from 3 sources (~30011 ms interval)"
    ),
}


@responses.activate
def test_cadence_parses_engine_payload(prophet):
    register_token()
    responses.add(responses.GET, CADENCE_URL, json=_CADENCE, status=200)

    c = prophet.explore.egress.cadence(["sentinel-910724", "sentinel-284391"], "google")

    assert isinstance(c, Cadence)
    assert c.status == "success"
    assert c.results_for == ["sentinel-910724", "sentinel-284391"]

    assert len(c.cdf) == 7
    assert isinstance(c.cdf[0], CdfPoint)
    assert c.cdf[3].gap_secs == 30.0044
    assert c.cdf[3].fraction == 0.5

    assert [d.gap_secs for d in c.dominant_intervals] == [30.0044, 118.4471]
    assert c.dominant_intervals[0].fraction == 0.7
    assert c.steppedness == 0.7
    assert c.median_gap_secs == 30.0044

    assert c.stats["stats.timing.inter_arrival_secs.regularity"] == 0.4183
    assert c.stats["stats.timing.inter_arrival_secs.mean_gap"] == 47.3312

    assert isinstance(c.beacon, Beacon)
    assert c.beacon.flows == 1284
    assert c.beacon.sources == 3
    assert c.beacon.interval_ms == 30011.4
    assert c.readout.startswith("machine-steady")

    body = json.loads(responses.calls[-1].request.body)
    assert body["instance_ids"] == ["sentinel-910724", "sentinel-284391"]


@responses.activate
def test_cadence_sparse_data_payload(prophet):
    """The engine's <3-quantile-points shape: empty rhythm, null steppedness/median."""
    register_token()
    responses.add(
        responses.GET,
        CADENCE_URL,
        json={
            "status": "success",
            "results_for": ["sentinel-910724"],
            "timestamp": "2026-07-06T21:14:09.482913+00:00",
            "cdf": [],
            "dominant_intervals": [],
            "steppedness": None,
            "median_gap_secs": None,
            "stats": {},
            "beacon": {"flows": 0, "sources": 0, "interval_ms": None},
            "readout": "no cadence data",
        },
        status=200,
    )

    c = prophet.explore.egress.cadence("sentinel-910724", "google")
    assert c.cdf == []
    assert c.dominant_intervals == []
    assert c.steppedness is None
    assert c.median_gap_secs is None
    assert c.stats == {}
    assert c.beacon is not None
    assert c.beacon.flows == 0
    assert c.beacon.interval_ms is None


@responses.activate
def test_cadence_absent_keys_do_not_raise(prophet):
    """Tolerant contract: every rhythm key optional, so a lean payload validates."""
    register_token()
    responses.add(responses.GET, CADENCE_URL, json={"status": "success"}, status=200)

    c = prophet.explore.egress.cadence("sentinel-910724", "google")
    assert c.cdf == []
    assert c.dominant_intervals == []
    assert c.steppedness is None
    assert c.median_gap_secs is None
    assert c.stats == {}
    assert c.beacon is None
    assert c.readout is None


@responses.activate
def test_cadence_extra_fields_tolerated(prophet):
    """A field added within a minor API version must flow through, not raise."""
    register_token()
    payload = {**_CADENCE, "future_field": {"nested": 1}}
    payload["cdf"] = [{"gap_secs": 1.5, "fraction": 0.5, "future_pointwise": True}]
    responses.add(responses.GET, CADENCE_URL, json=payload, status=200)

    c = prophet.explore.egress.cadence("sentinel-910724", "google")
    assert c.model_extra == {"future_field": {"nested": 1}}
    assert c.cdf[0].model_extra == {"future_pointwise": True}


def test_cadence_model_has_no_stale_distribution_field():
    """The pre-rewrite histogram `distribution` field must be gone."""
    assert "distribution" not in Cadence.model_fields
    assert set(Cadence.model_fields) == {
        # envelope (shared with every egress result)
        "status", "results_for", "timestamp", "readout",
        # cadence payload — must mirror the engine op exactly
        "cdf", "dominant_intervals", "steppedness", "median_gap_secs", "stats", "beacon",
    }


def test_cadence_requires_org(prophet):
    with pytest.raises(ValidationError):
        prophet.explore.egress.cadence("sentinel-910724", "")
