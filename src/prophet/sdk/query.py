"""PQL Query Builder for constructing flow queries."""

from __future__ import annotations

from enum import Enum
from typing import Any, Union


class Operator(Enum):
    """PQL operators."""

    EQ = "eq"
    NE = "ne"
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"
    EX = "ex"
    NEX = "nex"
    IN = "in"
    WI = "wi"
    NWI = "nwi"


class _FieldBuilder:
    """Builder for a single field condition."""

    def __init__(self, field: str, parent: Q) -> None:
        self._field = field
        self._parent = parent

    def eq(self, value: Union[str, int, float]) -> Q:
        """Equal to (field eq value)."""
        self._parent._add_condition(self._field, Operator.EQ, value)
        return self._parent

    def ne(self, value: Union[str, int, float]) -> Q:
        """Not equal to (field ne value)."""
        self._parent._add_condition(self._field, Operator.NE, value)
        return self._parent

    def gt(self, value: Union[int, float]) -> Q:
        """Greater than (field gt value)."""
        self._parent._add_condition(self._field, Operator.GT, value)
        return self._parent

    def lt(self, value: Union[int, float]) -> Q:
        """Less than (field lt value)."""
        self._parent._add_condition(self._field, Operator.LT, value)
        return self._parent

    def gte(self, value: Union[int, float]) -> Q:
        """Greater than or equal (field gte value)."""
        self._parent._add_condition(self._field, Operator.GTE, value)
        return self._parent

    def lte(self, value: Union[int, float]) -> Q:
        """Less than or equal (field lte value)."""
        self._parent._add_condition(self._field, Operator.LTE, value)
        return self._parent

    def exists(self) -> Q:
        """Field exists (field ex)."""
        self._parent._add_condition(self._field, Operator.EX, None)
        return self._parent

    def not_exists(self) -> Q:
        """Field does not exist (field nex)."""
        self._parent._add_condition(self._field, Operator.NEX, None)
        return self._parent

    def in_(self, values: list[Union[str, int]]) -> Q:
        """Value in list (field in [val1, val2])."""
        self._parent._add_condition(self._field, Operator.IN, values)
        return self._parent

    def wildcard(self, pattern: str) -> Q:
        """Wildcard match (field wi pattern)."""
        self._parent._add_condition(self._field, Operator.WI, pattern)
        return self._parent

    def not_wildcard(self, pattern: str) -> Q:
        """Not wildcard match (field nwi pattern)."""
        self._parent._add_condition(self._field, Operator.NWI, pattern)
        return self._parent


class Q:
    """
    Fluent PQL query builder.

    Examples:
        # Simple query
        Q("dst.port").eq(443)

        # Compound query
        Q("dst.port").eq(443).and_("bytes").gt(1000)

        # Grouped query
        inner = Q("protocol").eq("tcp").or_("protocol").eq("udp")
        Q.group(inner).and_("dst.port").eq(443)

        # Raw PQL
        Q.raw("dst.ip eq 10.90.8.53")
    """

    def __init__(self, field: str | None = None) -> None:
        """
        Create a new query builder.

        Args:
            field: Optional field name to start the query
        """
        self._parts: list[str] = []
        self._pending_conjunction: str | None = None
        self._pending_field: str | None = field

    @classmethod
    def group(cls, query: Q) -> Q:
        """
        Create a new query starting with a grouped sub-query.

        Args:
            query: Another Q instance to wrap in parentheses

        Returns:
            New Q instance with the group
        """
        instance = cls()
        instance._parts.append(f"({query.build()})")
        return instance

    @classmethod
    def raw(cls, pql: str) -> Q:
        """
        Create a query from a raw PQL string.

        Args:
            pql: Raw PQL query string

        Returns:
            Q instance containing the raw query
        """
        instance = cls()
        instance._parts.append(pql)
        return instance

    def _get_field_builder(self, name: str) -> _FieldBuilder:
        """Get a field builder for the given field name."""
        return _FieldBuilder(name, self)

    def _add_condition(self, field: str, op: Operator, value: Any) -> None:
        """Add a condition to the query."""
        # Add pending conjunction if any
        if self._pending_conjunction and self._parts:
            self._parts.append(self._pending_conjunction)
            self._pending_conjunction = None

        # Format the condition
        condition = self._format_condition(field, op, value)
        self._parts.append(condition)

    def _format_condition(self, field: str, op: Operator, value: Any) -> str:
        """Format a single condition as PQL string."""
        if op in (Operator.EX, Operator.NEX):
            return f"{field} {op.value}"

        if op == Operator.IN:
            # Format list: field in [val1, val2, val3]
            formatted_values = ", ".join(self._format_value(v) for v in value)
            return f"{field} {op.value} [{formatted_values}]"

        return f"{field} {op.value} {self._format_value(value)}"

    def _format_value(self, value: Any) -> str:
        """Format a value for PQL."""
        if isinstance(value, str):
            # Don't quote strings in PQL - the backend handles this
            return value
        return str(value)

    # Operator methods that use the pending field
    def eq(self, value: Union[str, int, float]) -> Q:
        """Equal to (field eq value)."""
        if self._pending_field is None:
            raise ValueError("No field specified. Use Q('field_name').eq(value)")
        self._add_condition(self._pending_field, Operator.EQ, value)
        self._pending_field = None
        return self

    def ne(self, value: Union[str, int, float]) -> Q:
        """Not equal to (field ne value)."""
        if self._pending_field is None:
            raise ValueError("No field specified")
        self._add_condition(self._pending_field, Operator.NE, value)
        self._pending_field = None
        return self

    def gt(self, value: Union[int, float]) -> Q:
        """Greater than (field gt value)."""
        if self._pending_field is None:
            raise ValueError("No field specified")
        self._add_condition(self._pending_field, Operator.GT, value)
        self._pending_field = None
        return self

    def lt(self, value: Union[int, float]) -> Q:
        """Less than (field lt value)."""
        if self._pending_field is None:
            raise ValueError("No field specified")
        self._add_condition(self._pending_field, Operator.LT, value)
        self._pending_field = None
        return self

    def gte(self, value: Union[int, float]) -> Q:
        """Greater than or equal (field gte value)."""
        if self._pending_field is None:
            raise ValueError("No field specified")
        self._add_condition(self._pending_field, Operator.GTE, value)
        self._pending_field = None
        return self

    def lte(self, value: Union[int, float]) -> Q:
        """Less than or equal (field lte value)."""
        if self._pending_field is None:
            raise ValueError("No field specified")
        self._add_condition(self._pending_field, Operator.LTE, value)
        self._pending_field = None
        return self

    def exists(self) -> Q:
        """Field exists (field ex)."""
        if self._pending_field is None:
            raise ValueError("No field specified")
        self._add_condition(self._pending_field, Operator.EX, None)
        self._pending_field = None
        return self

    def not_exists(self) -> Q:
        """Field does not exist (field nex)."""
        if self._pending_field is None:
            raise ValueError("No field specified")
        self._add_condition(self._pending_field, Operator.NEX, None)
        self._pending_field = None
        return self

    def in_(self, values: list[Union[str, int]]) -> Q:
        """Value in list (field in [val1, val2])."""
        if self._pending_field is None:
            raise ValueError("No field specified")
        self._add_condition(self._pending_field, Operator.IN, values)
        self._pending_field = None
        return self

    def wildcard(self, pattern: str) -> Q:
        """Wildcard match (field wi pattern)."""
        if self._pending_field is None:
            raise ValueError("No field specified")
        self._add_condition(self._pending_field, Operator.WI, pattern)
        self._pending_field = None
        return self

    def not_wildcard(self, pattern: str) -> Q:
        """Not wildcard match (field nwi pattern)."""
        if self._pending_field is None:
            raise ValueError("No field specified")
        self._add_condition(self._pending_field, Operator.NWI, pattern)
        self._pending_field = None
        return self

    # Conjunction methods
    def and_(self, field: str | None = None) -> Q:
        """
        Add AND conjunction.

        Args:
            field: Optional field name for next condition

        Returns:
            Self for chaining
        """
        self._pending_conjunction = "and"
        if field:
            self._pending_field = field
        return self

    def or_(self, field: str | None = None) -> Q:
        """
        Add OR conjunction.

        Args:
            field: Optional field name for next condition

        Returns:
            Self for chaining
        """
        self._pending_conjunction = "or"
        if field:
            self._pending_field = field
        return self

    def add_group(self, query: Q) -> Q:
        """
        Add a grouped sub-query.

        Args:
            query: Another Q instance to wrap in parentheses

        Returns:
            Self for chaining
        """
        if self._pending_conjunction and self._parts:
            self._parts.append(self._pending_conjunction)
            self._pending_conjunction = None
        self._parts.append(f"({query.build()})")
        return self

    def build(self) -> str:
        """
        Build the final PQL query string.

        Returns:
            Complete PQL query string
        """
        return " ".join(self._parts)

    def is_empty(self) -> bool:
        """Check if query has no conditions."""
        return len(self._parts) == 0

    def __str__(self) -> str:
        return self.build()

    def __repr__(self) -> str:
        return f"Q({self.build()!r})"
