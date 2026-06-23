"""Shared fixtures + helpers for HTTP-mocked SDK tests."""

from __future__ import annotations

import base64
import json
import time

import pytest
import responses

from prophet.sdk import Prophet

BASE_URL = "https://test.prophet.io"
TOKEN_URL = f"{BASE_URL}/rest/oauth2/token/1.0"


def make_jwt(aud: str = "test-parent", scopes: list[str] | None = None) -> str:
    """Build an unsigned-but-well-formed JWT whose payload carries `aud` + scopes."""
    def seg(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    header = seg({"alg": "RS256", "typ": "JWT", "kid": "k", "cid": aud})
    payload = seg({
        "aud": aud,
        "scopes": scopes or ["p.token.scope.node_api"],
        "exp": int(time.time()) + 3600,
    })
    return f"{header}.{payload}.signature"


def register_token(aud: str = "test-parent") -> None:
    """Register the OAuth2 token endpoint on the active responses mock."""
    responses.add(
        responses.POST,
        TOKEN_URL,
        json={
            "access_token": make_jwt(aud),
            "expires_in": 3600,
            "expires_at": int(time.time()) + 3600,
            "token_type": "Bearer",
        },
        status=200,
    )


@pytest.fixture(autouse=True)
def _isolate_collector_cache(tmp_path, monkeypatch):
    """Point the collector binary cache at a per-test temp dir, never ~/.cache."""
    monkeypatch.setenv("PROPHET_SDK_CACHE_DIR", str(tmp_path / "_cache"))


@pytest.fixture
def prophet() -> Prophet:
    """A client pointed at the test base URL with retries disabled (fast failures)."""
    return Prophet(
        base_url=BASE_URL,
        client_id="test-client",
        client_secret="test-secret",
        max_retries=0,
    )
