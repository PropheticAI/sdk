"""Data models for flow records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Pydantic Base Config
# =============================================================================


class FlowModel(BaseModel):
    """Base model for all flow-related models."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
    )


# =============================================================================
# Geo Models
# =============================================================================


class GeoLatLon(FlowModel):
    """Geographic coordinates."""

    lat: float | None = None
    lon: float | None = None


class GeoEntry(FlowModel):
    """Geographic information for an IP address."""

    continent_name: str | None = None
    country_iso_code: str | None = None
    country_name: str | None = None
    city_name: str | None = None
    time_zone: str | None = None
    location_network: str | None = None
    asn: int | None = None
    org: str | None = None
    as_network: str | None = None
    accuracy_radius: int | None = None
    location: GeoLatLon | None = None


# =============================================================================
# Classification Context
# =============================================================================


class ClassificationContext(FlowModel):
    """Context information for classification."""

    organization: str | None = None
    industry: str | None = None
    fqdn: str | None = None
    id: int | None = None
    method: str | None = None
    vector: list[float] | None = None


# =============================================================================
# Direction Fields (src/dst)
# =============================================================================


class DirectionFields(FlowModel):
    """Source or destination endpoint information."""

    ip: str | None = None
    port: int | None = None
    address_type: str | None = None
    geo: GeoEntry | None = None
    ctx: ClassificationContext | None = None


# =============================================================================
# IP and Transport
# =============================================================================


class IP(FlowModel):
    """IP layer information."""

    version: int | None = None


class Transport(FlowModel):
    """Transport layer information."""

    proto: str | None = None
    proto_num: int | None = None


# =============================================================================
# Sensor and Path
# =============================================================================


class Sensor(FlowModel):
    """Sensor information."""

    id: str | None = None
    type: str | None = None
    name: str | None = None
    hostname: str | None = None
    interface: str | None = None


class Acl(FlowModel):
    """ACL event information."""

    event_id: int | None = None
    event_map: str | None = None
    action: str | None = None


class Path(FlowModel):
    """Network path information."""

    sensor: Sensor | None = None
    acl: Acl | None = None
    ingress_vrf_id: int | None = None
    egress_vrf_id: int | None = None
    ip_next_hop: str | None = None
    ip_bgp_next_hop: str | None = None
    src_tos: int | None = None
    dst_tos: int | None = None
    src_as: int | None = None
    dst_as: int | None = None
    src_net: int | None = None
    dst_net: int | None = None
    src_vlan: int | None = None
    dst_vlan: int | None = None
    src_mac: str | None = None
    dst_mac: str | None = None
    src_snmp: int | None = None
    dst_snmp: int | None = None
    forwarding_status_id: int | None = None
    forwarding_status: str | None = None
    forwarding_reason: str | None = None


# =============================================================================
# Meta
# =============================================================================


class Meta(FlowModel):
    """Flow metadata."""

    ingest_time: int | None = Field(None, alias="@ingest_time")
    customer_id: str | None = None
    tags: list[str] | None = None
    flow_types: list[str] | None = None
    time_of_day: int | None = None
    day_of_week: int | None = None
    flipped: bool | None = None


# =============================================================================
# Threat
# =============================================================================


class Threat(FlowModel):
    """Threat intelligence information."""

    indicator: str | None = None
    type: str | None = None
    trajectory: str | None = None
    ip: str | None = None
    mask: int | None = None
    posture: list[str] | None = None
    tags: list[str] | None = None
    feeds: list[str] | None = None
    countermeasures: list[str] | None = None


# =============================================================================
# Beacon
# =============================================================================


class ScaleAnalysis(FlowModel):
    """Beacon scale analysis results."""

    beacon_score: float | None = None
    timing_regularity: float | None = None
    timing_predictability: float | None = None
    timing_uniformity: float | None = None
    pattern_significance: float | None = None
    is_beacon: bool | None = None
    sample_count: int | None = None
    analysis_type: str | None = None


class BeaconInterval(FlowModel):
    """Beacon interval information."""

    value_ms: int | None = None


class BeaconMeta(FlowModel):
    """Beacon detection metadata."""

    detection_engine: str | None = None
    analysis_version: str | None = None


class BeaconData(FlowModel):
    """Beacon detection data."""

    confidence: float | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    packet_level: ScaleAnalysis | None = None
    session_level: ScaleAnalysis | None = None
    primary_evidence: str | None = None
    has_sessions: bool | None = None
    weighted_confidence: float | None = None
    consensus_score: float | None = None
    interval: BeaconInterval | None = None
    meta: BeaconMeta | None = None


# =============================================================================
# Protocol-Specific
# =============================================================================


class StreamingStats(FlowModel):
    """Streaming statistical moments."""

    count: int | None = None
    sum: float | None = None
    sum_squares: float | None = None
    sum_cubes: float | None = None


class CustomTcpProto(FlowModel):
    """TCP protocol details."""

    flags: list[str] | None = None
    window_length: StreamingStats | None = None


class IcmpProto(FlowModel):
    """ICMP protocol details."""

    type: int | None = None
    type_map: str | None = None
    code: int | None = None


class NatProto(FlowModel):
    """NAT protocol details."""

    event: int | None = None
    event_map: str | None = None
    xdst_ip: str | None = None
    xdst_port: int | None = None
    xsrc_ip: str | None = None
    xsrc_port: int | None = None


class MplsProto(FlowModel):
    """MPLS protocol details."""

    top_label_ip: str | None = None
    top_label_type: int | None = None
    top_label_prefix_len: int | None = None
    count: int | None = None
    label_1: int | None = Field(None, alias="1_label")
    label_2: int | None = Field(None, alias="2_label")
    label_3: int | None = Field(None, alias="3_label")
    label_4: int | None = Field(None, alias="4_label")
    label_5: int | None = Field(None, alias="5_label")
    label_6: int | None = Field(None, alias="6_label")
    last_ttl: int | None = None
    last_label: int | None = None


class Encap(FlowModel):
    """Encapsulation details."""

    src_ip: str | None = None
    src_port: int | None = None
    dst_ip: str | None = None
    dst_port: int | None = None
    proto: int | None = None
    proto_map: str | None = None
    ipv6_src_ip: str | None = None
    ipv6_dst_ip: str | None = None


# =============================================================================
# Suricata
# =============================================================================


class SuricataFlowEvent(FlowModel):
    """Suricata flow event."""

    community_id: str | None = None
    event_type: str | None = None
    alerted: bool | None = None


class SuricataFields(FlowModel):
    """Suricata-specific fields."""

    flow_id: int | None = None
    l7_app_map: str | None = None
    event_types: list[str] | None = None
    flow: SuricataFlowEvent | None = None


# =============================================================================
# Session Metrics (stats)
# =============================================================================


class StatisticalMoments(FlowModel):
    """Statistical moments for streaming calculations."""

    count: int | None = None
    sum: float | None = None
    sum_squares: float | None = None
    sum_cubes: float | None = None


class DirectionalStats(FlowModel):
    """Directional statistics with src/dst breakdown."""

    src: StatisticalMoments | None = None
    dst: StatisticalMoments | None = None
    total: float | None = None


class DirectionalValues(FlowModel):
    """Simple directional values."""

    src: float | None = None
    dst: float | None = None
    total: float | None = None


class VolumeMetrics(FlowModel):
    """Volume metrics (bytes and packets)."""

    bytes: DirectionalStats | None = None
    packets: DirectionalValues | None = None


class RateMetrics(FlowModel):
    """Rate metrics (bps and pps)."""

    bps: DirectionalValues | None = None
    pps: DirectionalValues | None = None


class LatencyMetrics(FlowModel):
    """RTT/Latency metrics."""

    net: StatisticalMoments | None = None
    app: StatisticalMoments | None = None


class RetransMetrics(FlowModel):
    """Retransmission metrics."""

    packets: float | None = None
    bytes: float | None = None


class QualityMetrics(FlowModel):
    """Connection quality metrics."""

    retrans: RetransMetrics | None = None
    fragments: float | None = None


class SessionSizeMetrics(FlowModel):
    """Session size metrics."""

    packet: StatisticalMoments | None = None
    frame: StatisticalMoments | None = None
    payload_entropy: StatisticalMoments | None = None


class InterArrivalMetrics(FlowModel):
    """Inter-arrival time metrics."""

    mean_gap: float | None = None
    regularity: float | None = None
    consistency: float | None = None
    burstiness: float | None = None
    min_gap: float | None = None
    max_gap: float | None = None


class TimingMetrics(FlowModel):
    """Timing metrics."""

    duration_secs: StatisticalMoments | None = None
    inter_arrival_secs: InterArrivalMetrics | None = None


class SessionMetrics(FlowModel):
    """Complete session metrics (stats field)."""

    connection_count: int | None = None
    volume: VolumeMetrics | None = None
    rate: RateMetrics | None = None
    rtt_secs: LatencyMetrics | None = None
    quality: QualityMetrics | None = None
    size: SessionSizeMetrics | None = None
    timing: TimingMetrics | None = None


# =============================================================================
# Simple Metrics (backward compatibility)
# =============================================================================


class SimpleMetrics(FlowModel):
    """Simple metrics (metric field) for backward compatibility."""

    src_bytes: float | None = None
    dst_bytes: float | None = None
    total_bytes: float | None = None


# =============================================================================
# Main Flow Model
# =============================================================================


class Flow(FlowModel):
    """
    Complete ProphetFlow record.

    This model matches the JSON structure serialized from the Go ProphetFlow struct.
    All fields are optional since flows may have varying levels of detail.
    """

    # Core identifiers
    id: str | None = None
    doc_type: str | None = None
    timestamp: int | None = Field(None, alias="@timestamp")
    key: str | None = None
    session_key: str | None = None

    # Application
    app_name: str | None = None

    # Endpoints
    src: DirectionFields | None = None
    dst: DirectionFields | None = None

    # Network layers
    ip: IP | None = None
    transport: Transport | None = None

    # Path and routing
    path: list[Path] | None = None

    # Threat intelligence
    threat: Threat | None = None

    # Beacon detection
    beacon: BeaconData | None = None

    # Metadata
    meta: Meta | None = None

    # Protocol-specific
    icmp: IcmpProto | None = None
    tcp: CustomTcpProto | None = None
    nat: NatProto | None = None
    mpls: MplsProto | None = None
    encap: Encap | None = None

    # Suricata
    suricata: SuricataFields | None = None

    # Metrics
    stats: SessionMetrics | None = None
    metric: SimpleMetrics | None = None

    # Convenience properties
    @property
    def timestamp_dt(self) -> datetime | None:
        """Get timestamp as datetime object."""
        if self.timestamp is None:
            return None
        return datetime.fromtimestamp(self.timestamp / 1000)

    @property
    def bytes(self) -> float:
        """Get total bytes (from metric or stats)."""
        if self.metric and self.metric.total_bytes is not None:
            return self.metric.total_bytes
        if self.stats and self.stats.volume and self.stats.volume.bytes:
            return self.stats.volume.bytes.total or 0
        return 0

    @property
    def packets(self) -> float:
        """Get total packets."""
        if self.stats and self.stats.volume and self.stats.volume.packets:
            return self.stats.volume.packets.total or 0
        return 0

    @property
    def src_ip(self) -> str:
        """Shortcut to source IP."""
        return self.src.ip if self.src else ""

    @property
    def dst_ip(self) -> str:
        """Shortcut to destination IP."""
        return self.dst.ip if self.dst else ""

    @property
    def src_port(self) -> int:
        """Shortcut to source port."""
        return self.src.port if self.src and self.src.port else 0

    @property
    def dst_port(self) -> int:
        """Shortcut to destination port."""
        return self.dst.port if self.dst and self.dst.port else 0

    @property
    def protocol(self) -> str:
        """Get transport protocol."""
        return self.transport.proto if self.transport else ""

    @property
    def instance_id(self) -> str:
        """Get instance/customer ID."""
        return self.meta.customer_id if self.meta else ""

    def __repr__(self) -> str:
        return (
            f"Flow({self.src_ip}:{self.src_port} -> "
            f"{self.dst_ip}:{self.dst_port}, bytes={self.bytes})"
        )


# =============================================================================
# Page Models
# =============================================================================


@dataclass
class FlowPage:
    """A page of flow results."""

    flows: list[Flow]
    found: int
    total: int
    returned: int
    current_page: int
    page_count: int
    has_more: bool
    took: float
    instance_id: str

    @classmethod
    def from_response(cls, data: dict[str, Any], instance_id: str) -> FlowPage:
        """Create FlowPage from API response data for a single instance."""
        raw_flows = data.get("flows", [])
        flows = [Flow.model_validate(f) for f in raw_flows]
        return cls(
            flows=flows,
            found=data.get("found", 0),
            total=data.get("total", 0),
            returned=data.get("returned", len(flows)),
            current_page=data.get("current_page", 0),
            page_count=data.get("pages", 1),
            has_more=data.get("more_data_available", False),
            took=data.get("took", 0.0),
            instance_id=instance_id,
        )
