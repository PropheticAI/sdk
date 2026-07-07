"""Flow iterator for pagination handling."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from ..exceptions import APIError, AuthenticationError, parse_error
from .models import Flow, FlowPage

if TYPE_CHECKING:
    from ..client import Prophet
    from ..models import Sort, TimeFilter
    from ..query import Q


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
        instance: str,
        query: str | Q,
        start: TimeFilter | None,
        end: TimeFilter | None,
        sort: list[Sort] | None,
        fields: list[str] | None,
        size: int,
    ) -> None:
        self._client = client
        self._instance = instance
        self._query = query.build() if hasattr(query, 'build') else query
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

    def collect(self, limit: int | None = None) -> list[Flow]:
        """
        Collect results into a list. EAGER — pass a `limit` (or call take() first)
        to bound memory on large result sets; an unbounded collect() buffers the
        entire match in RAM.

        Args:
            limit: Maximum number of flows to collect (None = all matches)

        Returns:
            List of Flow objects
        """
        if limit is not None:
            self._limit = limit
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
            "instance_ids": [self._instance],
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

        # Handle errors. The search-api wraps errors in a nested envelope —
        # {"error": {"code", "message", "type", "details"}, "timestamp": ...} —
        # which parse_error prefers, falling back to the older flat
        # {"error": "...", "code": "..."} shape.
        status = response.status_code
        if status in (400, 401, 403):
            try:
                body = response.json()
            except Exception:  # non-JSON error body — parse_error falls back
                body = None
            if status == 401:
                message, kind, details = parse_error(body, "Authentication failed")
                raise AuthenticationError(message=message, code=kind, details=details)
            if status == 403:
                message, kind, details = parse_error(body, "Authorization failed")
                raise APIError(
                    message=message,
                    status_code=403,
                    error_type=kind or "authorization_error",
                    details=details,
                )
            message, kind, details = parse_error(body, "Validation failed")
            raise APIError(
                message=message,
                status_code=400,
                error_type=kind or "validation_error",
                details=details,
            )

        if response.status_code != 200:
            raise APIError(
                message=f"Search request failed with status {response.status_code}",
                status_code=response.status_code,
            )

        data = response.json()
        instance_data = data.get(self._instance, {})
        return FlowPage.from_response(instance_data, self._instance)

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
