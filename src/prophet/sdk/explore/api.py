"""Explore ▸ Egress API — external-organization communication shape.

Read-only, descriptive: which external services a network sends traffic to, and
the texture of each relationship (when, rhythm, transfer, who/what, how). Merged
across the requested instances. Not detection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from ..exceptions import APIError, ValidationError, raise_for_response
from .models import (
    Access,
    Cadence,
    OrganizationHeader,
    OrganizationList,
    Reach,
    Temporal,
    Transfer,
)

if TYPE_CHECKING:
    from ..client import Prophet
    from ..models import TimeFilter

_BASE = "/rest/explore/1.0/egress"


def _instances(instances: str | list[str]) -> list[str]:
    ids = [instances] if isinstance(instances, str) else list(instances or [])
    ids = [i for i in ids if i]
    if not ids:
        raise ValidationError("instances is required (a customer id or list of ids)")
    return ids


def _body(
    instances: str | list[str],
    start: TimeFilter | None,
    end: TimeFilter | None,
    *,
    size: int | None = None,
    src_ip: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"instance_ids": _instances(instances)}
    if start is not None:
        body["start"] = start.to_dict()
    if end is not None:
        body["end"] = end.to_dict()
    if size is not None:
        body["size"] = size
    if src_ip:
        body["src_ip"] = src_ip
    return body


def _require_org(org: str) -> None:
    if not org:
        raise ValidationError("org is required")


class EgressAPI:
    """External-organization communication shape. Accessed via ``prophet.explore.egress``.

    Example:
        from prophet.sdk import Prophet, HoursAgo, Now

        prophet = Prophet(client_id="...", client_secret="...")

        orgs = prophet.explore.egress.organizations("acme_msp", start=HoursAgo(24))
        for o in orgs.organizations:
            print(o.name, o.upload, o.download)

        google = prophet.explore.egress.temporal("acme_msp", "google", start=HoursAgo(168))
        print(google.readout)
    """

    def __init__(self, client: Prophet) -> None:
        self._client = client

    # -- page 1: organizations ----------------------------------------------
    def organizations(
        self,
        instances: str | list[str],
        *,
        start: TimeFilter | None = None,
        end: TimeFilter | None = None,
        size: int = 25,
    ) -> OrganizationList:
        """External orgs the network sent traffic to, ranked by volume (merged)."""
        data = self._get("/organizations", _body(instances, start, end, size=size))
        return OrganizationList.model_validate(data)

    # -- per-org header ------------------------------------------------------
    def organization(
        self,
        instances: str | list[str],
        org: str,
        *,
        start: TimeFilter | None = None,
        end: TimeFilter | None = None,
        src_ip: str | None = None,
    ) -> OrganizationHeader:
        """Stable header attributes for one org (geo, industry, hosts, processes)."""
        _require_org(org)
        data = self._get(f"/organizations/{quote(org, safe='')}",
                         _body(instances, start, end, src_ip=src_ip))
        return OrganizationHeader.model_validate(data)

    # -- fingerprint dimensions ---------------------------------------------
    def temporal(self, instances, org, *, start=None, end=None, src_ip=None) -> Temporal:
        """WHEN: day-of-week × hour-of-day heatmap."""
        return Temporal.model_validate(self._dimension(instances, org, "temporal", start, end, src_ip))

    def cadence(self, instances, org, *, start=None, end=None, src_ip=None) -> Cadence:
        """RHYTHM: the session-gap CDF (stepped = machine) + beacon subset."""
        return Cadence.model_validate(self._dimension(instances, org, "cadence", start, end, src_ip))

    def transfer(self, instances, org, *, start=None, end=None, src_ip=None) -> Transfer:
        """WHAT'S MOVED: chunk size, entropy, duration, up/down."""
        return Transfer.model_validate(self._dimension(instances, org, "transfer", start, end, src_ip))

    def reach(self, instances, org, *, start=None, end=None, src_ip=None, size: int = 50) -> Reach:
        """WHO/WHAT: internal sources + processes reaching the org."""
        _require_org(org)
        data = self._get(f"/organizations/{quote(org, safe='')}/reach",
                         _body(instances, start, end, src_ip=src_ip, size=size))
        return Reach.model_validate(data)

    def access(self, instances, org, *, start=None, end=None, src_ip=None) -> Access:
        """HOW REACHED: TLS versions, ports, protocols, apps."""
        return Access.model_validate(self._dimension(instances, org, "access", start, end, src_ip))

    # -- internals -----------------------------------------------------------
    def _dimension(self, instances, org, dimension, start, end, src_ip) -> dict[str, Any]:
        _require_org(org)
        return self._get(
            f"/organizations/{quote(org, safe='')}/{dimension}",
            _body(instances, start, end, src_ip=src_ip),
        )

    def _get(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        response = self._client._request("GET", f"{_BASE}{path}", json=body)
        raise_for_response(response)
        if not response.text:
            raise APIError(
                f"Empty response from API (status={response.status_code})",
                status_code=response.status_code,
            )
        try:
            data: dict[str, Any] = response.json()
        except Exception:
            raise APIError(
                f"Invalid JSON response: {response.text[:500]}",
                status_code=response.status_code,
            ) from None
        return data


class ExploreAPI:
    """Explore APIs. Accessed via ``prophet.explore``.

    Groups the descriptive network-exploration surfaces. Currently exposes
    ``prophet.explore.egress`` (external-organization communication shape); more
    explore surfaces land here over time.
    """

    def __init__(self, client: Prophet) -> None:
        self._client = client
        self._egress = EgressAPI(client)

    @property
    def egress(self) -> EgressAPI:
        return self._egress
