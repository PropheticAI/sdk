"""Tests for data models."""

import pytest
from datetime import datetime

from prophet.sdk import (
    Now, HoursAgo, DaysAgo, MinutesAgo, WeeksAgo, At,
    Flow, FlowPage, Sort, DirectionFields, Transport, Meta,
    SessionMetrics, SimpleMetrics
)


class TestTimeFilters:
    """Test time filter models."""

    def test_now(self):
        now = Now()
        assert now.to_dict() == {"now": True}

    def test_hours_ago(self):
        t = HoursAgo(24)
        assert t.to_dict() == {"relative": {"value": 24, "unit": "hours"}}

    def test_days_ago(self):
        t = DaysAgo(7)
        assert t.to_dict() == {"relative": {"value": 7, "unit": "days"}}

    def test_minutes_ago(self):
        t = MinutesAgo(30)
        assert t.to_dict() == {"relative": {"value": 30, "unit": "minutes"}}

    def test_weeks_ago(self):
        t = WeeksAgo(2)
        assert t.to_dict() == {"relative": {"value": 2, "unit": "weeks"}}

    def test_at_string(self):
        t = At("2025-01-15T00:00:00Z")
        assert t.to_dict() == {"absolute": {"date": "2025-01-15T00:00:00Z"}}

    def test_at_datetime(self):
        dt = datetime(2025, 1, 15, 12, 30, 0)
        t = At(dt)
        assert t.to_dict() == {"absolute": {"date": "2025-01-15T12:30:00"}}

    def test_hours_ago_invalid(self):
        with pytest.raises(ValueError):
            HoursAgo(0)

    def test_hours_ago_negative(self):
        with pytest.raises(ValueError):
            HoursAgo(-1)


class TestSort:
    """Test Sort model."""

    def test_sort_default_order(self):
        s = Sort(field="@timestamp")
        assert s.to_dict() == {"field": "@timestamp", "order": "desc"}

    def test_sort_asc(self):
        s = Sort(field="bytes", order="asc")
        assert s.to_dict() == {"field": "bytes", "order": "asc"}

    def test_sort_invalid_order(self):
        with pytest.raises(ValueError):
            Sort(field="bytes", order="invalid")


class TestDirectionFields:
    """Test DirectionFields (src/dst) model."""

    def test_direction_fields_full(self):
        d = DirectionFields(ip="192.168.1.1", port=443, address_type="private")
        assert d.ip == "192.168.1.1"
        assert d.port == 443
        assert d.address_type == "private"

    def test_direction_fields_from_dict(self):
        data = {"ip": "10.0.0.1", "port": 80, "address_type": "public"}
        d = DirectionFields.model_validate(data)
        assert d.ip == "10.0.0.1"
        assert d.port == 80


class TestFlow:
    """Test Flow model with Pydantic parsing."""

    def test_flow_basic(self):
        data = {
            "id": "doc123",
            "@timestamp": 1706000000000,  # Unix ms
            "src": {"ip": "192.168.1.1", "port": 54321},
            "dst": {"ip": "10.90.8.53", "port": 53},
            "transport": {"proto": "UDP"},
            "app_name": "DNS",
            "metric": {"total_bytes": 512, "src_bytes": 100, "dst_bytes": 412},
        }
        flow = Flow.model_validate(data)

        assert flow.id == "doc123"
        assert flow.src_ip == "192.168.1.1"
        assert flow.src_port == 54321
        assert flow.dst_ip == "10.90.8.53"
        assert flow.dst_port == 53
        assert flow.protocol == "UDP"
        assert flow.app_name == "DNS"
        assert flow.bytes == 512

    def test_flow_timestamp_parsing(self):
        data = {"@timestamp": 1706000000000}  # Unix ms
        flow = Flow.model_validate(data)
        assert flow.timestamp == 1706000000000
        assert flow.timestamp_dt is not None
        assert flow.timestamp_dt.year == 2024

    def test_flow_timestamp_none(self):
        flow = Flow.model_validate({})
        assert flow.timestamp is None
        assert flow.timestamp_dt is None

    def test_flow_defaults(self):
        flow = Flow.model_validate({})
        assert flow.id is None
        assert flow.bytes == 0
        assert flow.packets == 0
        assert flow.app_name is None
        assert flow.src_ip == ""
        assert flow.dst_port == 0

    def test_flow_with_stats(self):
        data = {
            "stats": {
                "connection_count": 5,
                "volume": {
                    "bytes": {"total": 1024},
                    "packets": {"total": 10}
                },
                "rate": {
                    "bps": {"src": 100, "dst": 200, "total": 300}
                }
            }
        }
        flow = Flow.model_validate(data)
        assert flow.stats is not None
        assert flow.stats.connection_count == 5
        assert flow.stats.volume.bytes.total == 1024
        assert flow.stats.rate.bps.total == 300
        assert flow.bytes == 1024
        assert flow.packets == 10

    def test_flow_with_meta(self):
        data = {
            "meta": {
                "@ingest_time": 1706000000000,
                "customer_id": "test-instance",
                "tags": ["tag1", "tag2"],
                "flow_types": ["suricata"]
            }
        }
        flow = Flow.model_validate(data)
        assert flow.meta is not None
        assert flow.meta.customer_id == "test-instance"
        assert flow.meta.ingest_time == 1706000000000
        assert "tag1" in flow.meta.tags
        assert flow.instance_id == "test-instance"

    def test_flow_repr(self):
        data = {
            "src": {"ip": "192.168.1.1", "port": 54321},
            "dst": {"ip": "10.90.8.53", "port": 53},
            "metric": {"total_bytes": 512}
        }
        flow = Flow.model_validate(data)
        assert "192.168.1.1:54321" in repr(flow)
        assert "10.90.8.53:53" in repr(flow)

    def test_flow_extra_fields_allowed(self):
        """Test that extra fields don't cause errors."""
        data = {
            "id": "test",
            "unknown_field": "value",
            "another_unknown": {"nested": "data"}
        }
        flow = Flow.model_validate(data)
        assert flow.id == "test"


class TestFlowPage:
    """Test FlowPage model."""

    def test_from_response(self):
        data = {
            "flows": [
                {"id": "1", "metric": {"total_bytes": 100}},
                {"id": "2", "metric": {"total_bytes": 200}},
            ],
            "found": 100,
            "total": 10000,
            "returned": 2,
            "current_page": 0,
            "pages": 50,
            "more_data_available": True,
            "took": 0.15,
        }
        page = FlowPage.from_response(data, "instance-1")

        assert len(page.flows) == 2
        assert page.flows[0].id == "1"
        assert page.flows[0].bytes == 100
        assert page.found == 100
        assert page.total == 10000
        assert page.returned == 2
        assert page.current_page == 0
        assert page.page_count == 50
        assert page.has_more is True
        assert page.took == 0.15
        assert page.instance_id == "instance-1"
