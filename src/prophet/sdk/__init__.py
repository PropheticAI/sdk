"""
Prophet SDK - Python client for the Prophet API.

Example:
    from prophet.sdk import Prophet, Q, HoursAgo, Now

    prophet = Prophet(
        base_url="https://api.prophet.io",
        client_id="my_client",
        client_secret="my_secret"
    )

    # Query flows
    for flow in prophet.flows(
        instances=["instance-1"],
        query=Q("dst.port").eq(443),
        start=HoursAgo(24),
        end=Now(),
    ):
        print(f"{flow.src_ip}:{flow.src_port} -> {flow.dst_ip}:{flow.dst_port}")

    # Manage deployments
    response = prophet.deployments.list(parent_id="parent-123")
    for deployment in response.deployments:
        print(deployment.name)
"""

from .client import HealthStatus, Prophet
from .exceptions import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    ConnectionError,
    ProphetError,
    PQLSyntaxError,
    TimeoutError,
    TokenExpiredError,
    ValidationError,
)
from .models import (
    At,
    DaysAgo,
    HoursAgo,
    MinutesAgo,
    Now,
    Sort,
    TimeFilter,
    WeeksAgo,
)
from .query import Q

# Flow submodule exports
from .flows import (
    FlowIterator,
    FlowsAPI,
    Flow,
    FlowPage,
    DirectionFields,
    Transport,
    Meta,
    Threat,
    BeaconData,
    SessionMetrics,
    SimpleMetrics,
    GeoEntry,
    VolumeMetrics,
    RateMetrics,
    QualityMetrics,
    TimingMetrics,
)

# Deployment submodule exports
from .deployments import (
    DeploymentsAPI,
    Deployment,
    DeploymentListResponse,
    DeploymentCreateResponse,
    DeploymentDeleteResponse,
    ParentInfo,
)

__version__ = "0.1.0"

__all__ = [
    # Client
    "Prophet",
    "HealthStatus",
    # Query builder
    "Q",
    # Time filters
    "TimeFilter",
    "Now",
    "MinutesAgo",
    "HoursAgo",
    "DaysAgo",
    "WeeksAgo",
    "At",
    # Sort
    "Sort",
    # Flow API
    "FlowsAPI",
    "Flow",
    "FlowPage",
    "FlowIterator",
    "DirectionFields",
    "Transport",
    "Meta",
    "Threat",
    "BeaconData",
    "SessionMetrics",
    "SimpleMetrics",
    "GeoEntry",
    "VolumeMetrics",
    "RateMetrics",
    "QualityMetrics",
    "TimingMetrics",
    # Deployment API
    "DeploymentsAPI",
    "Deployment",
    "DeploymentListResponse",
    "DeploymentCreateResponse",
    "DeploymentDeleteResponse",
    "ParentInfo",
    # Exceptions
    "ProphetError",
    "ConfigurationError",
    "AuthenticationError",
    "TokenExpiredError",
    "APIError",
    "ValidationError",
    "PQLSyntaxError",
    "ConnectionError",
    "TimeoutError",
]
