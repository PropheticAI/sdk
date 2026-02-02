"""Tests for PQL query builder."""

import pytest

from prophet.sdk import Q


class TestQBasicOperators:
    """Test basic PQL operators."""

    def test_eq_string(self):
        query = Q("dst.ip").eq("10.90.8.53").build()
        assert query == "dst.ip eq 10.90.8.53"

    def test_eq_integer(self):
        query = Q("dst.port").eq(443).build()
        assert query == "dst.port eq 443"

    def test_ne(self):
        query = Q("protocol").ne("icmp").build()
        assert query == "protocol ne icmp"

    def test_gt(self):
        query = Q("bytes").gt(1024).build()
        assert query == "bytes gt 1024"

    def test_lt(self):
        query = Q("bytes").lt(1000000).build()
        assert query == "bytes lt 1000000"

    def test_gte(self):
        query = Q("packets").gte(10).build()
        assert query == "packets gte 10"

    def test_lte(self):
        query = Q("packets").lte(100).build()
        assert query == "packets lte 100"

    def test_exists(self):
        query = Q("app_name").exists().build()
        assert query == "app_name ex"

    def test_not_exists(self):
        query = Q("app_name").not_exists().build()
        assert query == "app_name nex"

    def test_in_list(self):
        query = Q("protocol").in_(["tcp", "udp"]).build()
        assert query == "protocol in [tcp, udp]"

    def test_wildcard(self):
        query = Q("hostname").wildcard("*server*").build()
        assert query == "hostname wi *server*"

    def test_not_wildcard(self):
        query = Q("hostname").not_wildcard("*test*").build()
        assert query == "hostname nwi *test*"


class TestQLogicalOperators:
    """Test logical operator combinations."""

    def test_and(self):
        query = Q("dst.ip").eq("10.90.8.53").and_("dst.port").eq(53).build()
        assert query == "dst.ip eq 10.90.8.53 and dst.port eq 53"

    def test_or(self):
        query = Q("protocol").eq("tcp").or_("protocol").eq("udp").build()
        assert query == "protocol eq tcp or protocol eq udp"

    def test_multiple_and(self):
        query = (
            Q("dst.port").eq(443)
            .and_("bytes").gt(1000)
            .and_("packets").gte(1)
            .build()
        )
        assert query == "dst.port eq 443 and bytes gt 1000 and packets gte 1"

    def test_mixed_and_or(self):
        query = (
            Q("dst.port").eq(443)
            .or_("dst.port").eq(80)
            .and_("bytes").gt(0)
            .build()
        )
        assert query == "dst.port eq 443 or dst.port eq 80 and bytes gt 0"


class TestQGrouping:
    """Test query grouping."""

    def test_simple_group(self):
        inner = Q("protocol").eq("tcp").or_("protocol").eq("udp")
        query = Q.group(inner).build()
        assert query == "(protocol eq tcp or protocol eq udp)"

    def test_group_with_and(self):
        inner = Q("protocol").eq("tcp").or_("protocol").eq("udp")
        query = Q.group(inner).and_("dst.port").eq(443).build()
        assert query == "(protocol eq tcp or protocol eq udp) and dst.port eq 443"

    def test_add_group_method(self):
        inner = Q("protocol").eq("tcp").or_("protocol").eq("udp")
        query = Q("dst.port").eq(443).and_().add_group(inner).build()
        assert query == "dst.port eq 443 and (protocol eq tcp or protocol eq udp)"


class TestQRaw:
    """Test raw PQL input."""

    def test_raw_query(self):
        query = Q.raw("dst.ip eq 10.90.8.53").build()
        assert query == "dst.ip eq 10.90.8.53"


class TestQStringConversion:
    """Test string conversion."""

    def test_str(self):
        q = Q("dst.port").eq(443)
        assert str(q) == "dst.port eq 443"

    def test_repr(self):
        q = Q("dst.port").eq(443)
        assert repr(q) == "Q('dst.port eq 443')"

    def test_is_empty(self):
        q = Q()
        assert q.is_empty()

    def test_not_empty(self):
        q = Q("dst.port").eq(443)
        assert not q.is_empty()


class TestQValidation:
    """Test query validation."""

    def test_no_field_raises(self):
        with pytest.raises(ValueError, match="No field specified"):
            Q().eq(443)
