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
    API for querying flow records.

    Accessed via `prophet.flows`.

    Example:
        for flow in prophet.flows.query(
            instances=["instance-1"],
            query=Q("dst.port").eq(443),
        ):
            print(flow.src_ip)
    """

    def __init__(self, client: Prophet) -> None:
        self._client = client

    def query(
        self,
        instances: list[str],
        query: str | Q = "",
        start: TimeFilter | None = None,
        end: TimeFilter | None = None,
        sort: list[Sort] | None = None,
        fields: list[str] | None = None,
        size: int = 100,
    ) -> FlowIterator:
        """
        Query flow records with automatic pagination.

        Args:
            instances: List of instance IDs to search
            query: PQL query string or Q builder (empty = match all)
            start: Start time filter (default: None)
            end: End time filter (default: None)
            sort: List of Sort specifications
            fields: Fields to include in response (None = all)
            size: Page size (default: 100, max: 25000)

        Returns:
            FlowIterator for iterating over results

        Example:
            for flow in prophet.flows.query(["inst-1"], Q("dst.port").eq(443)):
                print(flow.src.ip)
        """
        return FlowIterator(
            client=self._client,
            instances=instances,
            query=query,
            start=start,
            end=end,
            sort=sort,
            fields=fields,
            size=size,
        )

    def __call__(
        self,
        instances: list[str],
        query: str | Q = "",
        start: TimeFilter | None = None,
        end: TimeFilter | None = None,
        sort: list[Sort] | None = None,
        fields: list[str] | None = None,
        size: int = 100,
    ) -> FlowIterator:
        """
        Shortcut: prophet.flows(...) is equivalent to prophet.flows.query(...).

        This maintains backward compatibility with the original API.
        """
        return self.query(
            instances=instances,
            query=query,
            start=start,
            end=end,
            sort=sort,
            fields=fields,
            size=size,
        )
