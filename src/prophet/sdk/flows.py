"""Flow iterator and pagination handling."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterator

from .exceptions import APIError, AuthenticationError
from .models import Flow, FlowPage, Sort, TimeFilter
from .query import Q

if TYPE_CHECKING:
    from .client import Prophet


class FlowIterator:
    """
    Lazy iterator over flow records with automatic pagination.

    Supports:
    - Iteration: `for flow in iterator:`
    - Limiting: `iterator.take(100)`
    - First page: `iterator.first()`
    - Collect all: `iterator.collect()`
    - Manual pagination: `iterator.next_page()`
    """

    def __init__(
        self,
        client: Prophet,
        instances: list[str],
        query: str | Q,
        start: TimeFilter | None,
        end: TimeFilter | None,
        sort: list[Sort] | None,
        fields: list[str] | None,
        size: int,
    ) -> None:
        self._client = client
        self._instances = instances
        self._query = query.build() if isinstance(query, Q) else query
        self._start = start
        self._end = end
        self._sort = sort
        self._fields = fields
        self._size = size

        # Iteration state
        self._current_page: FlowPage | None = None
        self._page_num = 0
        self._flow_index = 0
        self._total_yielded = 0
        self._limit: int | None = None
        self._exhausted = False

    def take(self, n: int) -> FlowIterator:
        """
        Limit total results returned across all pages.

        Args:
            n: Maximum number of flows to return

        Returns:
            Self for chaining
        """
        self._limit = n
        return self

    def first(self) -> FlowPage:
        """
        Fetch and return only the first page.

        Returns:
            FlowPage containing the first page of results
        """
        return self._fetch_page(0)

    def collect(self) -> list[Flow]:
        """
        Collect all results into a list.

        Warning: Be careful with large result sets. Consider using
        take() to limit results first.

        Returns:
            List of all Flow objects
        """
        return list(self)

    def next_page(self) -> FlowPage | None:
        """
        Manually fetch the next page.

        Returns:
            FlowPage or None if no more pages
        """
        if self._exhausted:
            return None

        page = self._fetch_page(self._page_num)
        self._page_num += 1

        if not page.has_more:
            self._exhausted = True

        return page

    def __iter__(self) -> Iterator[Flow]:
        return self

    def __next__(self) -> Flow:
        # Check if we've hit the limit
        if self._limit is not None and self._total_yielded >= self._limit:
            raise StopIteration

        # Fetch first page if needed
        if self._current_page is None:
            self._current_page = self._fetch_page(0)
            self._page_num = 1

        # Move to next page if current page exhausted
        while self._flow_index >= len(self._current_page.flows):
            if not self._current_page.has_more:
                raise StopIteration
            self._current_page = self._fetch_page(self._page_num)
            self._page_num += 1
            self._flow_index = 0

        # Return next flow
        flow = self._current_page.flows[self._flow_index]
        self._flow_index += 1
        self._total_yielded += 1
        return flow

    def _fetch_page(self, page: int) -> FlowPage:
        """Make API request for a specific page."""
        # Build request payload
        payload: dict[str, Any] = {
            "instance_ids": self._instances,
            "module": "flows",
            "size": self._size,
            "page": page,
        }

        if self._query:
            payload["sentence"] = self._query

        if self._start is not None:
            payload["start"] = self._start.to_dict()

        if self._end is not None:
            payload["end"] = self._end.to_dict()

        if self._sort:
            payload["sort"] = [s.to_dict() for s in self._sort]

        if self._fields:
            payload["fields"] = self._fields

        # Make request
        response = self._client._request("POST", "/search/records/1.0", json=payload)

        # Handle errors
        if response.status_code == 401:
            data = response.json()
            raise AuthenticationError(
                message=data.get("error", "Authentication failed"),
                code=data.get("code"),
            )

        if response.status_code == 400:
            data = response.json()
            error = data.get("error", {})
            raise APIError(
                message=error.get("message", "Validation failed"),
                status_code=400,
                error_type="validation_error",
                details=error.get("details"),
            )

        if response.status_code != 200:
            raise APIError(
                message=f"Search request failed with status {response.status_code}",
                status_code=response.status_code,
            )

        data = response.json()

        # Get the first instance's results
        # (we query one instance at a time for the iterator)
        instance_id = self._instances[0]
        instance_data = data.get(instance_id, {})

        return FlowPage.from_response(instance_data, instance_id)

    @property
    def total_found(self) -> int | None:
        """
        Total matching documents (available after first fetch).

        Returns:
            Total count or None if not yet fetched
        """
        if self._current_page is None:
            return None
        return self._current_page.found
