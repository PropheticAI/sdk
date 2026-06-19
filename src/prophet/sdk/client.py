"""Main Prophet client."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .auth import TokenManager
from .deployments import DeploymentsAPI
from .exceptions import APIError, ConnectionError
from .flows import FlowsAPI
from .nodes import NodesAPI
from .profiles import ProfilesAPI

logger = logging.getLogger("prophet.sdk")


@dataclass
class HealthStatus:
    """API health check response."""

    status: str
    service: str
    version: str
    timestamp: str


class Prophet:
    """
    Python client for the Prophet API.

    Provides access to:
    - `prophet.flows` - Query flow records
    - `prophet.deployments` - Manage sub-deployments
    - `prophet.nodes` - Provision and inspect nodes
    - `prophet.profiles` - Manage node capture-config profiles

    Example:
        from prophet.sdk import Prophet, Q, HoursAgo, Now

        # base_url defaults to production (https://app.prophet.io);
        # pass base_url="https://dev.prophet.io" to target dev.
        prophet = Prophet(
            client_id="my_client",
            client_secret="my_secret",
        )

        # Query flows
        for flow in prophet.flows(
            instances=["instance-1"],
            query=Q("dst.port").eq(443),
            start=HoursAgo(24),
            end=Now(),
        ):
            print(f"{flow.src.ip} -> {flow.dst.ip}")

        # List deployments
        response = prophet.deployments.list(parent_id="parent-123")
        for d in response.deployments:
            print(d.name)
    """

    DEFAULT_BASE_URL = "https://app.prophet.io"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        client_id: str,
        client_secret: str,
        timeout: float = 30.0,
        refresh_threshold: int = 300,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize the Prophet client.

        Args:
            base_url: Base URL of the Prophet API (default: production, https://app.prophet.io)
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            timeout: Request timeout in seconds (default: 30)
            refresh_threshold: Seconds before token expiry to refresh (default: 300)
            max_retries: Retries for transient failures (429/5xx) on idempotent
                requests, with exponential backoff (default: 3). POST is not
                auto-retried, so provisioning never double-mints a credential.
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()

        # Retry transient failures on idempotent methods only (urllib3's default
        # allowed_methods excludes POST), so reads self-heal across blips but a
        # provision POST is never silently retried.
        retry = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        self._auth = TokenManager(
            base_url=self._base_url,
            client_id=client_id,
            client_secret=client_secret,
            session=self._session,
            refresh_threshold=refresh_threshold,
        )

        # Initialize API namespaces
        self._flows = FlowsAPI(self)
        self._deployments = DeploymentsAPI(self)
        self._nodes = NodesAPI(self)
        self._profiles = ProfilesAPI(self)

    @property
    def flows(self) -> FlowsAPI:
        """
        Access the Flows API for querying flow records.

        Returns:
            FlowsAPI instance

        Example:
            # Using .query() method
            for flow in prophet.flows.query(["inst-1"], Q("dst.port").eq(443)):
                print(flow.src.ip)

            # Or call directly (backward compatible)
            for flow in prophet.flows(["inst-1"], Q("dst.port").eq(443)):
                print(flow.src.ip)
        """
        return self._flows

    @property
    def deployments(self) -> DeploymentsAPI:
        """
        Access the Deployments API for managing sub-deployments.

        Returns:
            DeploymentsAPI instance

        Example:
            # List sub-deployments
            response = prophet.deployments.list(parent_id="parent-123")

            # Create a sub-deployment
            result = prophet.deployments.create(
                name="Sub Tenant",
                handle="sub_tenant",
                parent_id="parent-123",
            )
        """
        return self._deployments

    @property
    def nodes(self) -> NodesAPI:
        """
        Access the Nodes API for provisioning units and inspecting nodes.

        Returns:
            NodesAPI instance

        Example:
            unit = prophet.nodes.provision(
                deployment="child-customer-id",
                cpu_id="0x1122334455667788",
                profile_id="<profile-uuid>",
            )
            yaml_blob = unit.collector_yaml(spool_dir="/data/apps/prophet/spool")
        """
        return self._nodes

    @property
    def profiles(self) -> ProfilesAPI:
        """
        Access the Profiles API for managing capture-config templates.

        Returns:
            ProfilesAPI instance

        Example:
            profile = prophet.profiles.create(name="Fleet A")
        """
        return self._profiles

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
        logger.debug("%s %s", method, path)

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
