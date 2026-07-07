"""Data models for the Explore ▸ Egress API.

Typed mirrors of the external contract. Every model tolerates extra fields
(``extra="allow"``) so a field added within a minor API version flows through to
an older SDK without a validation error. Results are **merged** across the
requested instances; ``results_for`` echoes the scope covered.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Model(BaseModel):
    """Base with forward-compatible config shared by every egress model."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class _EgressResult(_Model):
    """Fields common to every egress response envelope."""

    status: str | None = None
    results_for: list[str] = []
    timestamp: str | None = None
    readout: str | None = None


# --- list -------------------------------------------------------------------
class OrganizationRow(_Model):
    name: str | None = None
    bytes: int = 0
    upload: int = 0
    download: int = 0
    flows: int = 0
    sources: int = 0


class Coverage(_Model):
    classified_in_page: int = 0
    total_flows: int = 0


class OrganizationList(_EgressResult):
    organizations: list[OrganizationRow] = []
    total_orgs: int = 0
    coverage: Coverage | None = None


# --- header -----------------------------------------------------------------
class OrganizationHeader(_EgressResult):
    org: str | None = None
    industry: str | None = None
    geo: str | None = None
    upload: int = 0
    download: int = 0
    sources: int = 0
    endpoints: int = 0
    processes: list[str] = []


# --- temporal ---------------------------------------------------------------
class MatrixCell(_Model):
    row: str | None = None
    col: str | None = None
    value: float = 0


class Temporal(_EgressResult):
    cells: list[MatrixCell] = []
    rows: list[str] = []
    cols: list[str] = []
    total: int = 0


# --- cadence ----------------------------------------------------------------
class CdfPoint(_Model):
    """A (gap, mass) point on the session-gap distribution.

    In ``Cadence.cdf``, ``fraction`` of sessions have a characteristic gap of
    at most ``gap_secs`` (cumulative). In ``Cadence.dominant_intervals`` the
    same shape names a beat: ``fraction`` is that interval's share of mass.
    """

    gap_secs: float = 0
    fraction: float = 0


class Beacon(_Model):
    flows: int = 0
    sources: int = 0
    interval_ms: float | None = None


class Cadence(_EgressResult):
    cdf: list[CdfPoint] = []
    dominant_intervals: list[CdfPoint] = []  # top beats (largest-mass first)
    steppedness: float | None = None         # mass of the largest beat (~1.0 = one scheduler)
    median_gap_secs: float | None = None     # p50 session gap
    stats: dict[str, Any] = {}               # keyed by dotted field path, e.g.
    #   "stats.timing.inter_arrival_secs.regularity" / ".mean_gap" / ".burstiness"
    beacon: Beacon | None = None


# --- transfer ---------------------------------------------------------------
class TransferFacts(_Model):
    chunk_bytes_mean: float | None = None
    chunk_cv: float | None = None
    entropy_mean: float | None = None
    duration_mean: float | None = None
    up: int = 0
    down: int = 0


class Transfer(_EgressResult):
    transfer: TransferFacts | None = None


# --- reach ------------------------------------------------------------------
class SourceRow(_Model):
    ip: str | None = None
    upload: int = 0
    download: int = 0
    flows: int = 0


class ProcessRow(_Model):
    name: str | None = None
    flows: int = 0
    sources: int = 0


class Reach(_EgressResult):
    sources: list[SourceRow] = []
    processes: list[ProcessRow] = []
    source_count: int = 0


# --- access -----------------------------------------------------------------
class TermRow(_Model):
    name: Any = None
    flows: int = 0
    bytes: int = 0


class Access(_EgressResult):
    tls_versions: list[TermRow] = []
    ports: list[TermRow] = []
    protocols: list[TermRow] = []
    apps: list[TermRow] = []
