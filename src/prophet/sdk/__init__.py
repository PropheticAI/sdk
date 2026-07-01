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
from .factory import FactoryAPI, Installer

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

# Investigations submodule exports
from .investigations import (
    AtAGlance,
    AttackRef,
    DecisionSupport,
    HostValue,
    Investigation,
    InvestigationListItem,
    InvestigationMeta,
    InvestigationPage,
    InvestigationsAPI,
    KeyFinding,
    OpenQuestion,
    Provenance,
    ProvenanceActor,
    ProvenanceLeg,
    RecommendedAction,
    TimelineEvent,
    TrafficLink,
    Trigger,
    TriggerSignal,
    Verdict,
)

# Explore submodule exports
from .explore import (
    Access,
    Beacon,
    Cadence,
    Coverage,
    EgressAPI,
    ExploreAPI,
    HistogramBucket,
    MatrixCell,
    OrganizationHeader,
    OrganizationList,
    OrganizationRow,
    ProcessRow,
    Reach,
    SourceRow,
    Temporal,
    TermRow,
    Transfer,
    TransferFacts,
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
    EnabledService,
    HostLogServices,
    NetflowServices,
    PacketServices,
    Profile,
    ProfilesAPI,
    ProfileServices,
    lightweight_packet_services,
)
from .query import Q

__version__ = "0.4.0"

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
    # Investigations API
    "InvestigationsAPI",
    "Investigation",
    "InvestigationListItem",
    "InvestigationPage",
    "Verdict",
    "AtAGlance",
    "Trigger",
    "TriggerSignal",
    "KeyFinding",
    "TimelineEvent",
    "TrafficLink",
    "Provenance",
    "ProvenanceLeg",
    "ProvenanceActor",
    "AttackRef",
    "HostValue",
    "OpenQuestion",
    "RecommendedAction",
    "DecisionSupport",
    "InvestigationMeta",
    # Explore API
    "ExploreAPI",
    "EgressAPI",
    "OrganizationList",
    "OrganizationRow",
    "OrganizationHeader",
    "Coverage",
    "Temporal",
    "MatrixCell",
    "Cadence",
    "Beacon",
    "HistogramBucket",
    "Transfer",
    "TransferFacts",
    "Reach",
    "SourceRow",
    "ProcessRow",
    "Access",
    "TermRow",
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
    "ProfileServices",
    "PacketServices",
    "NetflowServices",
    "HostLogServices",
    "EnabledService",
    # Collector API
    "CollectorAPI",
    # Factory workflow
    "FactoryAPI",
    "Installer",
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
