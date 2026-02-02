"""OAuth2 token management with automatic refresh."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import requests

from .exceptions import AuthenticationError

if TYPE_CHECKING:
    from requests import Session


class TokenManager:
    """Handles OAuth2 token lifecycle with automatic refresh."""

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        session: Session | None = None,
        refresh_threshold: int = 300,
    ) -> None:
        """
        Initialize token manager.

        Args:
            base_url: API base URL
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            session: Optional requests Session to use
            refresh_threshold: Seconds before expiry to trigger refresh (default: 300)
        """
        self._base_url = base_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._session = session or requests.Session()
        self._refresh_threshold = refresh_threshold
        self._token: str | None = None
        self._expires_at: float | None = None

    def get_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.

        Returns:
            Valid JWT access token string

        Raises:
            AuthenticationError: If token acquisition fails
        """
        if self._needs_refresh():
            self._fetch_token()
        assert self._token is not None
        return self._token

    def refresh(self) -> str:
        """
        Force token refresh regardless of expiration status.

        Returns:
            Fresh access token

        Raises:
            AuthenticationError: If refresh fails
        """
        self._fetch_token()
        assert self._token is not None
        return self._token

    def is_expired(self) -> bool:
        """Check if current token is expired."""
        if self._expires_at is None:
            return True
        return time.time() >= self._expires_at

    def _needs_refresh(self) -> bool:
        """Check if token should be refreshed (within threshold of expiry)."""
        if self._token is None or self._expires_at is None:
            return True
        return time.time() >= (self._expires_at - self._refresh_threshold)

    def _fetch_token(self) -> None:
        """Fetch a new token from the OAuth2 endpoint."""
        url = f"{self._base_url}/oauth2/token/1.0"
        payload = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }

        try:
            response = self._session.post(url, json=payload, timeout=30)
        except requests.RequestException as e:
            raise AuthenticationError(f"Failed to connect to auth server: {e}") from e

        if response.status_code == 401:
            data = response.json()
            raise AuthenticationError(
                message=data.get("error", "Invalid credentials"),
                code=data.get("code", "invalid_credentials"),
                details=data,
            )

        if response.status_code != 200:
            raise AuthenticationError(
                message=f"Token request failed with status {response.status_code}",
                code="token_request_failed",
                details={"status_code": response.status_code, "body": response.text},
            )

        data = response.json()
        self._token = data["access_token"]
        self._expires_at = float(data["expires_at"])

    def clear(self) -> None:
        """Clear cached token, forcing refresh on next access."""
        self._token = None
        self._expires_at = None
