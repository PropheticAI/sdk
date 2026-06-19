"""Data models for nodes and unit provisioning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class NodeModel(BaseModel):
    """Base model for node-related models (tolerates extra/forward-compat fields)."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class NodeConnection(NodeModel):
    """Live connectivity for a node."""

    control_plane: bool = False
    ingest: bool = False


class NodeHealth(NodeModel):
    """Last-reported health summary."""

    status: str | None = None
    last_seen_at: str | None = None


class Node(NodeModel):
    """
    A nodes-v2 node as returned by GET /rest/nodes/1.0.

    `status` is the factory pass/fail signal: a unit is fully enrolled and
    collecting once status == "active" and connection.control_plane is True.
    """

    node_id: str
    machine_id: str | None = None
    customer_id: str
    customer_name: str | None = None
    description: str | None = None
    # `| str` keeps forward-compat if the server adds a status we don't know yet.
    status: Literal["active", "pending_approval", "staged"] | str | None = None
    profile_id: str | None = None
    profile_name: str | None = None
    connection: NodeConnection = NodeConnection()
    collector_version: str | None = None
    update_channel: str | None = None
    update_available: bool | None = None
    latest_version: str | None = None
    health: NodeHealth = NodeHealth()

    @property
    def is_active(self) -> bool:
        """True once the node is approved/active (not pending_approval or staged)."""
        return self.status == "active"

    @property
    def is_enrolled(self) -> bool:
        """True once the node is active AND its control plane is live — the gate."""
        return self.is_active and self.connection.control_plane

    def __repr__(self) -> str:
        cp = self.connection.control_plane
        return f"Node({self.node_id}, status={self.status!r}, control_plane={cp})"


@dataclass(frozen=True)
class ProvisionedUnit:
    """
    Result of provisioning a unit. `access_key` is shown exactly once — store it
    in your ops DB and write it (with machine_id) into the unit's config.

    Immutable: the credential is read-once and should not be mutated in place.
    """

    access_key: str
    machine_id: str
    customer_id: str
    profile_id: str | None = None

    @classmethod
    def from_response(cls, data: dict[str, Any], *, machine_id: str) -> ProvisionedUnit:
        # The server echoes machine_id when given one; fall back to the value the
        # SDK derived/sent so the field is always populated for the caller.
        return cls(
            access_key=data["access_key"],
            machine_id=data.get("machine_id") or machine_id,
            customer_id=data["customer_id"],
            profile_id=data.get("profile_id"),
        )

    def collector_yaml(
        self,
        *,
        env: str = "prod",
        spool_dir: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """
        Render the prophet_collector.yaml the unit's flash step writes to disk.

        Pairs with a systemd unit that runs the bare `prophet` binary; all
        bootstrap config comes from this file.
        """
        lines = [
            f"env: {env}",
            f'access_key: "{self.access_key}"',
            f'machine_id: "{self.machine_id}"',
        ]
        if self.profile_id:
            lines.append(f'profile_id: "{self.profile_id}"')
        if spool_dir:
            lines.append(f"spool_dir: {spool_dir}")
        for key, value in (extra or {}).items():
            lines.append(f"{key}: {value}")
        return "\n".join(lines) + "\n"

    def __repr__(self) -> str:
        # Never echo the secret half of the access_key in logs/reprs.
        client_id = self.access_key.split(".", 1)[0]
        return (
            f"ProvisionedUnit(customer_id={self.customer_id!r}, "
            f"machine_id={self.machine_id!r}, client_id={client_id!r})"
        )
