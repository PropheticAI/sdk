"""
Prophet SDK - Python client for the Prophet API.

Example:
    from prophet.sdk import Prophet, Q, HoursAgo, Now

    # base_url defaults to production (https://app.prophet.io)
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
        print(f"{flow.src_ip}:{flow.src_port} -> {flow.dst_ip}:{flow.dst_port}")

    # Manage deployments
    for deployment in prophet.deployments.list():
        print(deployment.name)
"""

from .client import HealthStatus, Prophet
from .collector import CollectorAPI

# Deployment submodule exports
from .deployments import Deployment, DeploymentsAPI
from .exceptions import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    ConnectionError,
    PQLSyntaxError,
    ProphetError,
    TimeoutError,
    TokenExpiredError,
    ValidationError,
)

# Flow submodule exports
from .flows import (
    BeaconData,
    DirectionFields,
    Flow,
    FlowIterator,
    FlowPage,
    FlowsAPI,
    GeoEntry,
    Meta,
    QualityMetrics,
    RateMetrics,
    SessionMetrics,
    SimpleMetrics,
    Threat,
    TimingMetrics,
    Transport,
    VolumeMetrics,
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

# Nodes submodule exports
from .nodes import (
    Node,
    NodeConnection,
    NodeHealth,
    NodesAPI,
    ProvisionedUnit,
    derive_machine_id,
)

# Profiles submodule exports
from .profiles import (
    Profile,
    ProfilesAPI,
    lightweight_packet_services,
)
from .query import Q

__version__ = "0.3.0"

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
    # Nodes API
    "NodesAPI",
    "Node",
    "NodeConnection",
    "NodeHealth",
    "ProvisionedUnit",
    "derive_machine_id",
    # Profiles API
    "ProfilesAPI",
    "Profile",
    "lightweight_packet_services",
    # Collector API
    "CollectorAPI",
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
