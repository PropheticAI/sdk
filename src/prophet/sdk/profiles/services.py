"""
Typed, validated capture-config for profiles (input to profiles.create).

Every field is optional — a profile is a set of overrides, and the server fills
unset fields with its defaults — so only the values you set are sent
(to_payload() drops None). `extra="forbid"` means a misspelled field raises at
construction instead of silently no-op'ing server-side.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Config(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PacketServices(_Config):
    """Packet capture options."""

    enabled: bool | None = None
    interface_patterns: list[str] | None = None  # globs (e.g. ["eth*"]) matched per-node
    inspection: bool | None = None               # DPI: TCP reassembly + TLS/DNS (memory-heavy)
    payload: bool | None = None                  # extract cleartext HTTP body
    lightweight: bool | None = None              # reduce memory for constrained edge devices
    ephemeral: bool | None = None                # new identity each restart (K8s)
    afpacket: bool | None = None                 # AF_PACKET ring buffer (Linux)
    gre: bool | None = None                      # GRE/ERSPAN decapsulation
    process_ids: bool | None = None              # correlate packets with OS process IDs
    num_workers: int | None = None               # decoder goroutines (0 = auto)
    num_spoolers: int | None = None              # spooler goroutines (0 = auto)
    packet_buffer_length: int | None = None
    afpacket_block_size: int | None = None
    afpacket_num_blocks: int | None = None
    packet_buffer_timeout_ms: int | None = None
    max_spooled_files: int | None = None
    max_spooled_file_size: int | None = None
    ingest_stream_interval: int | None = None


class NetflowServices(_Config):
    """NetFlow/IPFIX collection options."""

    enabled: bool | None = None
    port: int | None = None


class EnabledService(_Config):
    """A simple on/off service (suricata logs / IDS)."""

    enabled: bool | None = None


class HostLogServices(_Config):
    """Host/journal log collection. Off by default."""

    enabled: bool | None = None
    # Sources to EXCLUDE — everything else for the node's OS is collected.
    excluded_sources: list[str] | None = None


class ProfileServices(_Config):
    """Full capture-config for a node profile; pass to profiles.create(services=...)."""

    packet: PacketServices | None = None
    netflow: NetflowServices | None = None
    suricata_logs: EnabledService | None = None
    suricata_ids: EnabledService | None = None
    host_logs: HostLogServices | None = None

    def to_payload(self) -> dict[str, Any]:
        """Serialize to the request body, omitting unset fields (server defaults win)."""
        return self.model_dump(exclude_none=True)
