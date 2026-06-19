"""Tests for flow querying + lazy pagination (single instance)."""

from __future__ import annotations

import json

import responses

from prophet.sdk import Q
from tests.conftest import BASE_URL, register_token

SEARCH_URL = f"{BASE_URL}/search/records/1.0"
INSTANCE = "inst-1"


def _page(flows: int, more: bool, found: int = 3) -> dict:
    """Build a single-instance search response page."""
    one = {"src": {"ip": "1.1.1.1"}, "dst": {"ip": "2.2.2.2", "port": 443}}
    return {INSTANCE: {
        "flows": [one for _ in range(flows)],
        "found": found,
        "more_data_available": more,
    }}


@responses.activate
def test_pagination_spans_pages(prophet):
    register_token()
    responses.add(responses.POST, SEARCH_URL, json=_page(2, more=True), status=200)
    responses.add(responses.POST, SEARCH_URL, json=_page(1, more=False), status=200)
    flows = list(prophet.flows.query(INSTANCE, query=Q("dst.port").eq(443)))
    assert len(flows) == 3


@responses.activate
def test_collect_limit_stops_early(prophet):
    register_token()
    # Only page 0 is registered; limit must stop before requesting page 1
    # (assert_all_requests_are_fired would fail if it over-fetched).
    responses.add(responses.POST, SEARCH_URL, json=_page(2, more=True), status=200)
    flows = prophet.flows.query(INSTANCE).collect(limit=2)
    assert len(flows) == 2


@responses.activate
def test_take_limits_results(prophet):
    register_token()
    responses.add(responses.POST, SEARCH_URL, json=_page(2, more=True), status=200)
    flows = prophet.flows.query(INSTANCE).take(1).collect()
    assert len(flows) == 1


@responses.activate
def test_request_sends_single_instance(prophet):
    register_token()
    responses.add(responses.POST, SEARCH_URL, json=_page(1, more=False), status=200)
    list(prophet.flows.query(INSTANCE))
    body = json.loads(responses.calls[-1].request.body)
    assert body["instance_ids"] == [INSTANCE]


@responses.activate
def test_first_page_reports_found(prophet):
    register_token()
    responses.add(responses.POST, SEARCH_URL, json=_page(1, more=False, found=42), status=200)
    page = prophet.flows.query(INSTANCE).first()
    assert page.found == 42


@responses.activate
def test_total_found_after_iteration(prophet):
    register_token()
    responses.add(responses.POST, SEARCH_URL, json=_page(1, more=False, found=42), status=200)
    it = prophet.flows.query(INSTANCE)
    assert it.total_found is None
    list(it)
    assert it.total_found == 42
