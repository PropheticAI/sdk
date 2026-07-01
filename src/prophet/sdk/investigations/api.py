"""Investigations API — read-only access to Apollo investigations."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..exceptions import APIError, ValidationError, raise_for_response
from .models import Investigation, InvestigationListItem, InvestigationPage

if TYPE_CHECKING:
    from ..client import Prophet

_BASE = "/rest/investigations/1.0"
_MAX_LIMIT = 200


def _iso(value: str | datetime | None) -> str | None:
    """Serialize a time filter to an ISO-8601 string the API accepts."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class InvestigationsAPI:
    """
    Read Apollo investigations for the authenticated tenant. Accessed via
    `prophet.investigations`. Read-only: the investigation is Apollo's analysis of a
    flagged event — verdict, findings, provenance lineage, and recommended actions.

    Example:
        # Most severe escalations first
        page = prophet.investigations.list(disposition="escalate", sort="recent")
        for inv in page:
            print(inv.headline)

        # Full detail, with convenience checks
        full = prophet.investigations.get(page.items[0].id)
        if full and full.needs_escalation:
            print(full.at_a_glance.therefore)

        # Stream every malicious investigation across all pages
        for inv in prophet.investigations.iter(disposition="malicious"):
            print(inv.id, inv.confidence)
    """

    def __init__(self, client: Prophet) -> None:
        self._client = client

    def list(
        self,
        *,
        disposition: str | None = None,
        min_confidence: float | None = None,
        since: str | datetime | None = None,
        until: str | datetime | None = None,
        sort: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> InvestigationPage:
        """
        List investigation rollups for the authenticated tenant.

        Args:
            disposition: filter by verdict — "benign", "malicious", or "escalate".
            min_confidence: only verdicts with confidence >= this (0..1).
            since / until: created-at window as an ISO-8601 string or datetime.
            sort: "severity" (default, most severe first) or "recent".
            limit: page size, clamped server-side to 1..200 (default 50).
            offset: page offset.

        Returns:
            InvestigationPage — iterable over InvestigationListItem, with `.total`,
            `.has_more`, and pagination fields.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if disposition is not None:
            params["disposition"] = disposition
        if min_confidence is not None:
            params["min_confidence"] = min_confidence
        since_iso = _iso(since)
        if since_iso is not None:
            params["since"] = since_iso
        until_iso = _iso(until)
        if until_iso is not None:
            params["until"] = until_iso
        if sort is not None:
            params["sort"] = sort

        response = self._client._request("GET", _BASE, params=params)
        raise_for_response(response)
        return InvestigationPage.model_validate(self._json(response))

    def iter(
        self,
        *,
        disposition: str | None = None,
        min_confidence: float | None = None,
        since: str | datetime | None = None,
        until: str | datetime | None = None,
        sort: str | None = None,
        page_size: int = 100,
        start_offset: int = 0,
    ) -> Iterator[InvestigationListItem]:
        """
        Stream investigation rollups across all pages (most severe first by default).

        Fetches one page at a time (page_size, capped at 200) and yields each item,
        advancing until the result set is exhausted. Handy for "process every
        escalated investigation" without manual offset bookkeeping.
        """
        page_size = max(1, min(page_size, _MAX_LIMIT))
        offset = max(0, start_offset)
        while True:
            page = self.list(
                disposition=disposition,
                min_confidence=min_confidence,
                since=since,
                until=until,
                sort=sort,
                limit=page_size,
                offset=offset,
            )
            if not page.investigations:
                return
            yield from page.investigations
            offset += len(page.investigations)
            if offset >= page.total:
                return

    def get(self, investigation_id: str) -> Investigation | None:
        """
        Fetch one full investigation by id.

        Returns None when the investigation does not exist, is not owned by the
        authenticated tenant, or has not finished yet (a running investigation has
        no summary — the full record is available once analysis completes).
        """
        if not investigation_id:
            raise ValidationError("investigation_id is required")

        response = self._client._request("GET", f"{_BASE}/{investigation_id}")
        if response.status_code == 404:
            return None
        raise_for_response(response)
        return Investigation.model_validate(self._json(response))

    @staticmethod
    def _json(response: Any) -> dict[str, Any]:
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
