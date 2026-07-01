"""Tests for the investigations API (read-only list / iter / get)."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import unquote

import pytest
import responses

from prophet.sdk import (
    Investigation,
    InvestigationListItem,
    InvestigationPage,
    ValidationError,
)
from tests.conftest import BASE_URL, register_token

INVESTIGATIONS_URL = f"{BASE_URL}/rest/investigations/1.0"

_ROW = {
    "id": "inv_1",
    "status": "completed",
    "disposition": "escalate",
    "confidence": 0.85,
    "headline": "Escalate: rclone exported ~3.7 GB to Google Drive.",
    "source": "10.90.8.16",
    "destination": "google",
    "detected_at": "2026-06-29T20:00:00Z",
    "created_at": "2026-06-30T22:46:37Z",
    "completed_at": "2026-06-30T23:01:09Z",
    "related_alerts_count": 0,
    "tags": ["exfil"],
}

_FULL = {
    "id": "inv_1",
    "status": "completed",
    "created_at": "2026-06-30T22:46:37Z",
    "completed_at": "2026-06-30T23:01:09Z",
    "trigger": {
        "source": "10.90.8.16",
        "destination": "google",
        "detected_at": "2026-06-29T20:00:00Z",
        "signal": {
            "volume_bytes": 616433024,
            "anomaly_score": 1,
            "surprise": 2.74,
            "mismatch": 4.7,
        },
    },
    "verdict": {"disposition": "escalate", "confidence": 0.85, "headline": "H", "rationale": "R"},
    "at_a_glance": {"known": "K", "unknown": "U", "therefore": "T"},
    "key_findings": [
        {
            "headline": "F",
            "observation": "O",
            "significance": "S",
            "role": "decisive",
            "importance": "high",
            "rules_out": ["Sanctioned backup"],
            "confirms": [],
            "timeline": [{"at": "2026-06-29T19:59:56Z", "label": "start"}],
            "traffic_links": [
                {"label": "flows", "rationale": "r", "query": {"query": "src.ip eq 10.90.8.16"}},
            ],
        }
    ],
    "provenance": {
        "available": True,
        "headline": "PH",
        "host": "marketing1",
        "completeness": 0.8,
        "host_value": {"role": "dev host", "value": "moderate", "reach": "keys"},
        "legs": [
            {
                "stage": "exfiltration",
                "title": "Exfiltration",
                "headline": "LH",
                "detail": None,
                "confidence": "directly_observed",
                "gap_reason": None,
                "at": "2026-06-29T19:59:56Z",
                "actors": [{"kind": "process", "label": "rclone"}],
                "attack": [
                    {
                        "tactic": "Exfiltration",
                        "technique_id": "T1567.002",
                        "technique": "Exfil to Cloud",
                    }
                ],
                "pivot_keys": ["uid=1002"],
            }
        ],
    },
    "decision_support": {
        "confidence_limits": "CL",
        "what_would_change_the_verdict": "WWC",
        "open_questions": [{"question": "Q", "needed_data": "logs", "priority": "high"}],
        "recommended_actions": [{"timeframe": "within_4h", "action": "A"}],
    },
    "meta": {
        "generated_at": "2026-06-30T23:01:09Z",
        "ai_generated": True,
        "analysis_version": "v2",
    },
}


def _page(items, total=None, limit=50, offset=0):
    return {
        "investigations": items,
        "total": total if total is not None else len(items),
        "limit": limit,
        "offset": offset,
    }


@responses.activate
def test_list_returns_page(prophet):
    register_token()
    responses.add(responses.GET, INVESTIGATIONS_URL, json=_page([_ROW], total=1), status=200)

    page = prophet.investigations.list()
    assert isinstance(page, InvestigationPage)
    assert page.total == 1
    assert len(page) == 1
    assert isinstance(page.items[0], InvestigationListItem)
    assert list(page)[0].id == "inv_1"
    assert page.items[0].needs_escalation is True
    assert page.has_more is False


@responses.activate
def test_page_has_more(prophet):
    register_token()
    responses.add(
        responses.GET,
        INVESTIGATIONS_URL,
        json=_page([_ROW], total=5, limit=1, offset=0),
        status=200,
    )
    page = prophet.investigations.list(limit=1)
    assert page.has_more is True


@responses.activate
def test_list_forwards_and_serializes_filters(prophet):
    register_token()
    responses.add(responses.GET, INVESTIGATIONS_URL, json=_page([]), status=200)

    prophet.investigations.list(
        disposition="malicious",
        min_confidence=0.5,
        sort="recent",
        limit=25,
        offset=10,
        since=datetime(2026, 4, 9, 22, 0, tzinfo=timezone.utc),
    )
    url = unquote(responses.calls[-1].request.url)
    assert "disposition=malicious" in url
    assert "min_confidence=0.5" in url
    assert "sort=recent" in url
    assert "limit=25" in url
    assert "offset=10" in url
    assert "since=2026-04-09T22:00:00+00:00" in url  # datetime serialized to ISO-8601


@responses.activate
def test_iter_paginates_across_pages(prophet):
    register_token()
    rows = [{**_ROW, "id": f"inv_{i}"} for i in range(3)]
    responses.add(
        responses.GET,
        INVESTIGATIONS_URL,
        json=_page(rows[:2], total=3, limit=2, offset=0),
        status=200,
    )
    responses.add(
        responses.GET,
        INVESTIGATIONS_URL,
        json=_page(rows[2:], total=3, limit=2, offset=2),
        status=200,
    )

    got = list(prophet.investigations.iter(page_size=2))
    assert [i.id for i in got] == ["inv_0", "inv_1", "inv_2"]


@responses.activate
def test_get_returns_full_investigation(prophet):
    register_token()
    responses.add(responses.GET, f"{INVESTIGATIONS_URL}/inv_1", json=_FULL, status=200)

    inv = prophet.investigations.get("inv_1")
    assert isinstance(inv, Investigation)
    assert inv.disposition == "escalate"
    assert inv.confidence == 0.85
    assert inv.needs_escalation is True
    assert inv.is_malicious is False
    assert inv.has_provenance is True
    assert inv.trigger.signal.volume_bytes == 616433024
    assert inv.key_findings[0].role == "decisive"
    assert inv.key_findings[0].rules_out == ["Sanctioned backup"]
    assert inv.key_findings[0].traffic_links is not None
    assert inv.key_findings[0].traffic_links[0].query == {"query": "src.ip eq 10.90.8.16"}
    assert inv.provenance is not None
    assert inv.provenance.legs[0].stage == "exfiltration"
    assert inv.provenance.legs[0].confidence == "directly_observed"
    assert inv.decision_support.what_would_change_the_verdict == "WWC"


@responses.activate
def test_get_404_returns_none(prophet):
    register_token()
    responses.add(
        responses.GET, f"{INVESTIGATIONS_URL}/missing", json={"code": "not_found"}, status=404
    )
    assert prophet.investigations.get("missing") is None


def test_get_empty_id_raises(prophet):
    with pytest.raises(ValidationError):
        prophet.investigations.get("")


@responses.activate
def test_running_investigation_props(prophet):
    register_token()
    row = {
        **_ROW,
        "id": "inv_run",
        "status": "running",
        "disposition": None,
        "confidence": None,
        "headline": None,
    }
    responses.add(responses.GET, INVESTIGATIONS_URL, json=_page([row]), status=200)

    item = prophet.investigations.list().items[0]
    assert item.is_running is True
    assert item.is_complete is False
    assert item.needs_escalation is False
    assert item.disposition is None


@responses.activate
def test_extra_fields_tolerated(prophet):
    """A field the SDK does not model must not break validation (forward-compat)."""
    register_token()
    row = {**_ROW, "future_field": {"nested": 1}}
    responses.add(responses.GET, INVESTIGATIONS_URL, json=_page([row]), status=200)

    item = prophet.investigations.list().items[0]
    assert item.id == "inv_1"
    assert item.model_extra == {"future_field": {"nested": 1}}
