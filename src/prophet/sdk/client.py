"""Main Prophet client."""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .auth import TokenManager
from .collector import CollectorAPI
from .deployments import DeploymentsAPI
from .exceptions import APIError, AuthenticationError, ConnectionError
from .explore import ExploreAPI
from .factory import FactoryAPI
from .flows import FlowsAPI
from .investigations import InvestigationsAPI
from .nodes import NodesAPI
from .profiles import ProfilesAPI

logger = logging.getLogger("prophet.sdk")


def _jwt_aud(token: str) -> str:
    """Decode the `aud` claim from a JWT payload without verifying the signature."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        aud = json.loads(base64.urlsafe_b64decode(payload)).get("aud")
    except Exception as e:
        raise AuthenticationError("could not decode token payload") from e
    if not isinstance(aud, str) or not aud:
        raise AuthenticationError("token has no 'aud' (customer_id) claim")
    return aud


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
    - `prophet.investigations` - Read Apollo investigations
    - `prophet.explore` - External-organization communication shape (egress)
    - `prophet.deployments` - Manage sub-deployments
    - `prophet.nodes` - Provision and inspect nodes
    - `prophet.profiles` - Manage node capture-config profiles
    - `prophet.collector` - Download the prophet-node binary
    - `prophet.factory` - End-to-end unit-provisioning workflows

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
            instance="instance-1",
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
        self._investigations = InvestigationsAPI(self)
        self._explore = ExploreAPI(self)
        self._deployments = DeploymentsAPI(self)
        self._nodes = NodesAPI(self)
        self._profiles = ProfilesAPI(self)
        self._collector = CollectorAPI(self)
        self._factory = FactoryAPI(self)

    @property
    def flows(self) -> FlowsAPI:
        """
        Access the Flows API for querying flow records.

        Returns:
            FlowsAPI instance

        Example:
            # Using .query() method
            for flow in prophet.flows.query("inst-1", Q("dst.port").eq(443)):
                print(flow.src.ip)

            # Or call directly
            for flow in prophet.flows("inst-1", Q("dst.port").eq(443)):
                print(flow.src.ip)
        """
        return self._flows

    @property
    def investigations(self) -> InvestigationsAPI:
        """
        Access the Investigations API for reading Apollo investigations.

        Returns:
            InvestigationsAPI instance

        Example:
            # List the newest escalations
            for inv in prophet.investigations.list(disposition="escalate", sort="recent"):
                print(inv.headline)

            # Fetch one full investigation
            full = prophet.investigations.get("inv_43d67a...")
            if full and full.needs_escalation:
                print(full.at_a_glance.therefore)
        """
        return self._investigations

    @property
    def deployments(self) -> DeploymentsAPI:
        """
        Access the Deployments API for managing sub-deployments.

        Returns:
            DeploymentsAPI instance

        Example:
            # List sub-deployments (parent_id defaults to prophet.customer_id)
            for d in prophet.deployments.list():
                print(d.name, d.customer_id)

            # Create a sub-deployment
            child = prophet.deployments.create(name="Sub Tenant", handle="sub_tenant")
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

    @property
    def collector(self) -> CollectorAPI:
        """
        Access the Collector API for downloading the prophet-node binary.

        Returns:
            CollectorAPI instance

        Example:
            binary = prophet.collector.download(arch="arm7", extract=True, dest="./dist")
        """
        return self._collector

    @property
    def factory(self) -> FactoryAPI:
        """
        Access the Factory API — end-to-end workflows that compose the primitives.

        Returns:
            FactoryAPI instance

        Example:
            inst = prophet.factory.build(
                deployment_id="child-customer-id", cpu_id="0x11..",
                profile_id="<uuid>", serial="SN-0042", arch="arm7",
            )
        """
        return self._factory

    @property
    def explore(self) -> ExploreAPI:
        """
        Access the Explore API — descriptive external-traffic characterization.

        Returns:
            ExploreAPI instance

        Example:
            orgs = prophet.explore.egress.organizations("acme_msp", start=HoursAgo(24))
            for o in orgs.organizations:
                print(o.name, o.upload, o.download)
        """
        return self._explore

    @property
    def customer_id(self) -> str:
        """
        The authenticated tenant's customer_id (the JWT `aud` claim).

        For a parent MSP this is the value you pass as `parent_id` when managing
        sub-deployments. Triggers a token fetch on first access.
        """
        return _jwt_aud(self._auth.get_token())

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
        **kwargs: Any,
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

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
