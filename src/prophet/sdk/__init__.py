"""
Prophet SDK - Python client for the Prophet Go-Search API.

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
        print(f"{flow.src_ip}:{flow.src_port} -> {flow.dst_ip}:{flow.dst_port}")
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
from .flows import FlowIterator
from .models import (
    # Time filters
    At,
    DaysAgo,
    HoursAgo,
    MinutesAgo,
    Now,
    TimeFilter,
    WeeksAgo,
    # Sort
    Sort,
    # Flow models
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
    # Supporting models
    VolumeMetrics,
    RateMetrics,
    QualityMetrics,
    TimingMetrics,
)
from .query import Q

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
    # Flow models
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
