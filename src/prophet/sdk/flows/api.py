"""Flows API for querying flow records."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .iterator import FlowIterator

if TYPE_CHECKING:
    from ..client import Prophet
    from ..models import Sort, TimeFilter
    from ..query import Q


class FlowsAPI:
    """
    API for querying flow records. Accessed via `prophet.flows`.

    Example:
        for flow in prophet.flows.query(
            instance="instance-1",
            query=Q("dst.port").eq(443),
        ):
            print(flow.src.ip)
    """

    def __init__(self, client: Prophet) -> None:
        self._client = client

    def query(
        self,
        instance: str,
        query: str | Q = "",
        start: TimeFilter | None = None,
        end: TimeFilter | None = None,
        sort: list[Sort] | None = None,
        fields: list[str] | None = None,
        size: int = 100,
    ) -> FlowIterator:
        """
        Query flow records for one instance, with automatic pagination.

        Args:
            instance: instance ID to search.
            query: PQL query string or Q builder (empty = match all).
            start: start time filter (default: None).
            end: end time filter (default: None).
            sort: list of Sort specifications.
            fields: fields to include in the response (None = all).
            size: page size (default: 100, max: 25000).

        Returns:
            FlowIterator over the matching flows.
        """
        return FlowIterator(
            client=self._client,
            instance=instance,
            query=query,
            start=start,
            end=end,
            sort=sort,
            fields=fields,
            size=size,
        )

    def __call__(
        self,
        instance: str,
        query: str | Q = "",
        start: TimeFilter | None = None,
        end: TimeFilter | None = None,
        sort: list[Sort] | None = None,
        fields: list[str] | None = None,
        size: int = 100,
    ) -> FlowIterator:
        """Shortcut: prophet.flows(...) is equivalent to prophet.flows.query(...)."""
        return self.query(
            instance=instance,
            query=query,
            start=start,
            end=end,
            sort=sort,
            fields=fields,
            size=size,
        )
