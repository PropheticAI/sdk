"""Main Prophet client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import requests

from .auth import TokenManager
from .exceptions import APIError, ConnectionError
from .flows import FlowIterator
from .models import Sort, TimeFilter
from .query import Q

if TYPE_CHECKING:
    pass


@dataclass
class HealthStatus:
    """API health check response."""

    status: str
    service: str
    version: str
    timestamp: str


class Prophet:
    """
    Python client for the Prophet Go-Search API.

    Example:
        from prophet.sdk import Prophet, Q, HoursAgo, Now

        prophet = Prophet(
            base_url="https://api.prophet.io",
            client_id="my_client",
            client_secret="my_secret"
        )

        for flow in prophet.flows(
            instances=["instance-1"],
            query=Q("dst.port").eq(443),
            start=HoursAgo(24),
            end=Now(),
        ):
            print(f"{flow.src.ip} -> {flow.dst.ip}")
    """

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        timeout: float = 30.0,
        refresh_threshold: int = 300,
    ) -> None:
        """
        Initialize the Prophet client.

        Args:
            base_url: Base URL of the Go-Search API
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            timeout: Request timeout in seconds (default: 30)
            refresh_threshold: Seconds before token expiry to refresh (default: 300)
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._auth = TokenManager(
            base_url=self._base_url,
            client_id=client_id,
            client_secret=client_secret,
            session=self._session,
            refresh_threshold=refresh_threshold,
        )

    def flows(
        self,
        instances: list[str],
        query: str | Q = "",
        start: TimeFilter | None = None,
        end: TimeFilter | None = None,
        sort: list[Sort] | None = None,
        fields: list[str] | None = None,
        size: int = 100,
    ) -> FlowIterator:
        """
        Query flow records with automatic pagination.

        Args:
            instances: List of instance IDs to search
            query: PQL query string or Q builder (empty = match all)
            start: Start time filter (default: None)
            end: End time filter (default: None)
            sort: List of Sort specifications
            fields: Fields to include in response (None = all)
            size: Page size (default: 100, max: 25000)

        Returns:
            FlowIterator for iterating over results

        Example:
            for flow in prophet.flows(["inst-1"], Q.field("dst.port").eq(443)):
                print(flow.src.ip)
        """
        return FlowIterator(
            client=self,
            instances=instances,
            query=query,
            start=start,
            end=end,
            sort=sort,
            fields=fields,
            size=size,
        )

    def health(self) -> HealthStatus:
        """
        Check API health status.

        Returns:
            HealthStatus with service information

        Raises:
            ConnectionError: If API is unreachable
            APIError: If health check fails
        """
        try:
            response = self._session.get(
                f"{self._base_url}/health",
                timeout=self._timeout,
            )
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to connect to API: {e}") from e

        if response.status_code != 200:
            raise APIError(
                message="Health check failed",
                status_code=response.status_code,
            )

        data = response.json()
        return HealthStatus(
            status=data.get("status", "unknown"),
            service=data.get("service", ""),
            version=data.get("version", ""),
            timestamp=data.get("timestamp", ""),
        )

    def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> requests.Response:
        """
        Make an authenticated request to the API.

        Args:
            method: HTTP method
            path: API path (e.g., "/search/records/1.0")
            **kwargs: Additional arguments passed to requests

        Returns:
            Response object
        """
        url = f"{self._base_url}{path}"

        # Get fresh token
        token = self._auth.get_token()

        # Set headers
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        headers["Content-Type"] = "application/json"

        # Set timeout if not specified
        if "timeout" not in kwargs:
            kwargs["timeout"] = self._timeout

        try:
            return self._session.request(method, url, headers=headers, **kwargs)
        except requests.RequestException as e:
            raise ConnectionError(f"Request failed: {e}") from e

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()

    def __enter__(self) -> Prophet:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
