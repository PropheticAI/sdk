"""Tests for flow querying + lazy pagination (single instance)."""

from __future__ import annotations

import json

import pytest
import responses

from prophet.sdk import APIError, AuthenticationError, Q
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


# --- search-api error envelopes ----------------------------------------------
# Auth errors arrive nested: {"error": {"code", "message", "type", "details"},
# "timestamp": ...}. The SDK must surface error.message / error.type / details,
# and must keep accepting the older flat {"error": "...", "code": "..."} shape.

def _nested(code: int, message: str, err_type: str, details: dict) -> dict:
    return {
        "error": {"code": code, "message": message, "type": err_type, "details": details},
        "timestamp": "2026-07-07T00:11:22.334455+00:00",
    }


@responses.activate
def test_search_401_nested_envelope(prophet):
    register_token()
    responses.add(
        responses.POST, SEARCH_URL, status=401,
        json=_nested(401, "Access token expired", "authentication_error",
                     {"reason": "token_expired"}),
    )
    with pytest.raises(AuthenticationError) as exc:
        list(prophet.flows.query(INSTANCE))
    assert exc.value.message == "Access token expired"  # not the dict repr
    assert exc.value.code == "authentication_error"
    assert exc.value.details == {"reason": "token_expired"}


@responses.activate
def test_search_403_insufficient_scope(prophet):
    register_token()
    responses.add(
        responses.POST, SEARCH_URL, status=403,
        json=_nested(403, "Token is missing the required scope", "authorization_error",
                     {"reason": "insufficient_scope",
                      "required_scope": "p.token.scope.search_api"}),
    )
    with pytest.raises(APIError) as exc:
        list(prophet.flows.query(INSTANCE))
    assert exc.value.status_code == 403
    assert exc.value.error_type == "authorization_error"
    assert exc.value.message == "Token is missing the required scope"
    assert exc.value.details["reason"] == "insufficient_scope"
    assert exc.value.details["required_scope"] == "p.token.scope.search_api"


@responses.activate
def test_search_403_instance_not_authorized(prophet):
    register_token()
    responses.add(
        responses.POST, SEARCH_URL, status=403,
        json=_nested(403, "Not authorized for 1 of the requested instances",
                     "authorization_error",
                     {"reason": "instance_not_authorized",
                      "unauthorized_instance_ids": ["sentinel-999999"]}),
    )
    with pytest.raises(APIError) as exc:
        list(prophet.flows.query(INSTANCE))
    assert exc.value.status_code == 403
    assert exc.value.error_type == "authorization_error"
    assert exc.value.details["unauthorized_instance_ids"] == ["sentinel-999999"]


@responses.activate
def test_search_401_flat_body_backward_compat(prophet):
    register_token()
    responses.add(
        responses.POST, SEARCH_URL, status=401,
        json={"error": "Authentication required", "code": "no_token"},
    )
    with pytest.raises(AuthenticationError) as exc:
        list(prophet.flows.query(INSTANCE))
    assert exc.value.message == "Authentication required"
    assert exc.value.code == "no_token"


@responses.activate
def test_search_400_nested_envelope(prophet):
    register_token()
    responses.add(
        responses.POST, SEARCH_URL, status=400,
        json=_nested(400, "PQL parse failure near 'eqq'", "validation_error",
                     {"position": 17}),
    )
    with pytest.raises(APIError) as exc:
        list(prophet.flows.query(INSTANCE))
    assert exc.value.status_code == 400
    assert exc.value.error_type == "validation_error"
    assert exc.value.message == "PQL parse failure near 'eqq'"
    assert exc.value.details == {"position": 17}
