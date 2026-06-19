"""Tests for client construction, auth/token, customer_id, and retry behavior."""

from __future__ import annotations

import pytest
import responses

from prophet.sdk import AuthenticationError, Prophet
from tests.conftest import BASE_URL, TOKEN_URL, register_token


def test_default_base_url_is_production():
    p = Prophet(client_id="x", client_secret="y")
    assert p._base_url == "https://app.prophet.io"


def test_credentials_are_keyword_only():
    with pytest.raises(TypeError):
        Prophet("https://app.prophet.io", "cid", "secret")  # type: ignore[misc]


def test_base_url_trailing_slash_stripped():
    p = Prophet(base_url="https://dev.prophet.io/", client_id="x", client_secret="y")
    assert p._base_url == "https://dev.prophet.io"


@responses.activate
def test_customer_id_decodes_jwt_aud(prophet):
    register_token(aud="parent-123")
    assert prophet.customer_id == "parent-123"


@responses.activate
def test_token_fetched_once_and_reused(prophet):
    register_token()
    responses.add(responses.GET, f"{BASE_URL}/rest/nodes/1.0", json={"nodes": []}, status=200)
    prophet.nodes.list()
    prophet.nodes.list()
    # Two node calls, but only ONE token mint (cached until near expiry).
    token_calls = [c for c in responses.calls if c.request.url == TOKEN_URL]
    assert len(token_calls) == 1


@responses.activate
def test_bad_credentials_raise_authentication_error(prophet):
    responses.add(responses.POST, TOKEN_URL, json={"error": "Invalid credentials"}, status=401)
    with pytest.raises(AuthenticationError):
        _ = prophet.customer_id


@responses.activate
def test_retries_transient_5xx_then_succeeds():
    # Idempotent GET should retry past a 503 to a 200.
    p = Prophet(base_url=BASE_URL, client_id="x", client_secret="y", max_retries=2)
    register_token()
    responses.add(responses.GET, f"{BASE_URL}/rest/nodes/1.0", status=503)
    responses.add(responses.GET, f"{BASE_URL}/rest/nodes/1.0", json={"nodes": []}, status=200)
    assert p.nodes.list() == []
