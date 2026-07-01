"""Data models for Apollo investigations.

Typed mirrors of the external Investigations API contract. Every model tolerates
extra fields (``extra="allow"``) so a field added within a minor API version flows
through to an older SDK without a validation error or a client upgrade.

Enum-ish fields (``disposition``, ``status``, ``role``, leg ``confidence``) are typed
as plain ``str`` on purpose — a new server-side value must not break an old client.
Use the convenience properties (``is_malicious`` etc.) for stable checks.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel, ConfigDict


class _Model(BaseModel):
    """Base with forward-compatible config shared by every investigation model."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")


# ---------------------------------------------------------------------------
# Trigger (the detection alert that started the investigation)
# ---------------------------------------------------------------------------
class TriggerSignal(_Model):
    """The detector's quantified reason for flagging (IRIS)."""

    volume_bytes: int | None = None
    anomaly_score: float | None = None
    surprise: float | None = None
    mismatch: float | None = None


class Trigger(_Model):
    source: str | None = None
    destination: str | None = None
    detected_at: str | None = None
    signal: TriggerSignal = TriggerSignal()


# ---------------------------------------------------------------------------
# Verdict + at-a-glance
# ---------------------------------------------------------------------------
class Verdict(_Model):
    disposition: str  # "benign" | "malicious" | "escalate"
    confidence: float
    headline: str
    rationale: str


class AtAGlance(_Model):
    """The investigation compressed to a Known / Unknown / Therefore syllogism."""

    known: str
    unknown: str | None = None
    therefore: str


# ---------------------------------------------------------------------------
# Key findings
# ---------------------------------------------------------------------------
class TimelineEvent(_Model):
    at: str
    label: str
    children: list[TimelineEvent] = []


class TrafficLink(_Model):
    """A replayable pointer into the underlying flows.

    ``query`` is the internal search query passed through with tenant fields
    stripped. Opaque/unstable in v1 — hold and replay it against the Search API,
    but do not depend on its shape.
    """

    label: str
    rationale: str | None = None
    query: dict[str, Any] | None = None


class KeyFinding(_Model):
    headline: str
    observation: str
    significance: str
    role: str | None = None  # decisive | supporting | ambiguous | context | data_gap
    importance: str | None = None  # high | medium | low
    rules_out: list[str] = []
    confirms: list[str] = []
    timeline: list[TimelineEvent] | None = None
    traffic_links: list[TrafficLink] | None = None


# ---------------------------------------------------------------------------
# Provenance (who / how / what lineage)
# ---------------------------------------------------------------------------
class ProvenanceActor(_Model):
    kind: str  # human | account | process | source_ip | tool | path | destination
    label: str
    detail: str | None = None


class AttackRef(_Model):
    tactic: str
    technique_id: str
    technique: str


class ProvenanceLeg(_Model):
    stage: str  # access | identity | execution | collection | exfiltration | lateral
    title: str
    headline: str
    detail: str | None = None
    confidence: str  # directly_observed | inferred | not_established
    gap_reason: str | None = None
    at: str | None = None
    actors: list[ProvenanceActor] = []
    attack: list[AttackRef] = []
    pivot_keys: list[str] = []


class HostValue(_Model):
    role: str
    value: str  # low | moderate | high
    reach: str | None = None


class Provenance(_Model):
    available: bool = False
    unavailable_reason: str | None = None
    headline: str | None = None
    host: str | None = None
    completeness: float = 0.0
    host_value: HostValue | None = None
    legs: list[ProvenanceLeg] = []


# ---------------------------------------------------------------------------
# Decision support
# ---------------------------------------------------------------------------
class OpenQuestion(_Model):
    question: str
    needed_data: str | None = None
    priority: str | None = None  # highest | high | medium | low


class RecommendedAction(_Model):
    timeframe: str
    action: str


class DecisionSupport(_Model):
    confidence_limits: str | None = None
    what_would_change_the_verdict: str | None = None
    open_questions: list[OpenQuestion] = []
    recommended_actions: list[RecommendedAction] = []


class InvestigationMeta(_Model):
    generated_at: str | None = None
    ai_generated: bool = True
    analysis_version: str | None = None


# ---------------------------------------------------------------------------
# Verdict convenience mixin
# ---------------------------------------------------------------------------
class _VerdictChecks:
    """Shared disposition/status convenience checks for the list item and the full
    investigation.

    Reads ``disposition``/``status`` off the concrete model via ``getattr`` — declaring
    them as annotations here would make pydantic treat them as fields on subclasses and
    collide with ``Investigation.disposition`` (a computed property, not a stored field).
    """

    @property
    def is_malicious(self) -> bool:
        return getattr(self, "disposition", None) == "malicious"

    @property
    def is_benign(self) -> bool:
        return getattr(self, "disposition", None) == "benign"

    @property
    def needs_escalation(self) -> bool:
        """True when Apollo could not settle intent and escalated to a human."""
        return getattr(self, "disposition", None) == "escalate"

    @property
    def is_running(self) -> bool:
        return getattr(self, "status", None) == "running"

    @property
    def is_complete(self) -> bool:
        return getattr(self, "status", None) == "completed"


# ---------------------------------------------------------------------------
# Top-level models
# ---------------------------------------------------------------------------
class InvestigationListItem(_Model, _VerdictChecks):
    """A compact rollup row from ``prophet.investigations.list()``."""

    id: str
    status: str  # running | completed | failed
    disposition: str | None = None  # benign | malicious | escalate (None while running)
    confidence: float | None = None
    headline: str | None = None
    source: str | None = None
    destination: str | None = None
    detected_at: str | None = None
    created_at: str | None = None
    completed_at: str | None = None
    related_alerts_count: int = 0
    tags: list[str] = []

    def __repr__(self) -> str:
        return f"InvestigationListItem({self.id}, {self.disposition or self.status})"


class Investigation(_Model, _VerdictChecks):
    """The full investigation from ``prophet.investigations.get(id)``."""

    id: str
    status: str  # running | completed | failed
    created_at: str | None = None
    completed_at: str | None = None
    trigger: Trigger = Trigger()
    verdict: Verdict | None = None
    at_a_glance: AtAGlance | None = None
    key_findings: list[KeyFinding] = []
    provenance: Provenance | None = None
    decision_support: DecisionSupport = DecisionSupport()
    meta: InvestigationMeta = InvestigationMeta()

    @property
    def disposition(self) -> str | None:
        """Apollo's verdict disposition, or None while running."""
        return self.verdict.disposition if self.verdict else None

    @property
    def confidence(self) -> float | None:
        return self.verdict.confidence if self.verdict else None

    @property
    def has_provenance(self) -> bool:
        """True when a host-log provenance chain was reconstructed."""
        return bool(self.provenance and self.provenance.available)

    def __repr__(self) -> str:
        return f"Investigation({self.id}, {self.disposition or self.status})"


class InvestigationPage(_Model):
    """One page of investigation rollups plus pagination metadata.

    Iterable and sized over its items, so ``for inv in page:`` and ``len(page)``
    work directly. Use ``prophet.investigations.iter(...)`` to stream across pages.
    """

    investigations: list[InvestigationListItem] = []
    total: int = 0
    limit: int = 0
    offset: int = 0

    @property
    def items(self) -> list[InvestigationListItem]:
        return self.investigations

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.investigations) < self.total

    def __iter__(self) -> Iterator[InvestigationListItem]:  # type: ignore[override]
        return iter(self.investigations)

    def __len__(self) -> int:
        return len(self.investigations)

    def __repr__(self) -> str:
        n = len(self.investigations)
        return f"InvestigationPage(items={n}, total={self.total}, offset={self.offset})"


# Resolve the recursive TimelineEvent.children reference.
TimelineEvent.model_rebuild()
