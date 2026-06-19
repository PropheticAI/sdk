"""Unit tests for the shared HTTP error -> exception mapping."""

from __future__ import annotations

import pytest

from prophet.sdk import APIError, AuthenticationError, ValidationError
from prophet.sdk.exceptions import raise_for_response


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, json_raises: bool = False):
        self.status_code = status_code
        self._payload = payload or {}
        self._json_raises = json_raises

    def json(self):
        if self._json_raises:
            raise ValueError("not JSON")
        return self._payload


def test_2xx_does_not_raise():
    raise_for_response(FakeResponse(200, {}))
    raise_for_response(FakeResponse(201, {}))


def test_401_maps_to_authentication_error():
    with pytest.raises(AuthenticationError):
        raise_for_response(FakeResponse(401, {"error": "bad creds", "code": "invalid"}))


def test_400_maps_to_validation_error():
    with pytest.raises(ValidationError):
        raise_for_response(FakeResponse(400, {"error": "missing field"}))


@pytest.mark.parametrize("status", [403, 404, 500, 502])
def test_other_errors_map_to_apierror_with_status(status):
    with pytest.raises(APIError) as exc:
        raise_for_response(FakeResponse(status, {"error": "boom"}))
    assert exc.value.status_code == status


def test_non_json_body_does_not_crash():
    # A bare 500 with an unparseable body must still raise APIError, not ValueError.
    with pytest.raises(APIError):
        raise_for_response(FakeResponse(500, json_raises=True))


def test_message_falls_back_when_no_error_field():
    with pytest.raises(APIError) as exc:
        raise_for_response(FakeResponse(503, {}))
    assert "503" in exc.value.message
