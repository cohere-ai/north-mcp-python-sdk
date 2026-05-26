"""Tests for north_mcp_python_sdk.telemetry helpers."""

from __future__ import annotations

import logging

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from unittest.mock import patch

from north_mcp_python_sdk import (
    Depends,
    NorthMCPServer,
    TelemetryConfig,
    get_telemetry_config,
)
from north_mcp_python_sdk.telemetry import (
    TraceContextFormatter,
    traced_span,
)


@pytest.fixture
def memory_exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def test_tracer(memory_exporter: InMemorySpanExporter) -> trace.Tracer:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory_exporter))
    trace.set_tracer_provider(provider)
    return provider.get_tracer("test")


def _exception_messages(span) -> list[str]:
    messages: list[str] = []
    for event in span.events:
        attrs = event.attributes or {}
        if "exception.message" in attrs:
            messages.append(str(attrs["exception.message"]))
    return messages


def test_traced_span_redacts_exception_details_by_default(
    test_tracer: trace.Tracer,
    memory_exporter: InMemorySpanExporter,
) -> None:
    with pytest.raises(ValueError, match="sensitive"):
        with traced_span(
            "test.span",
            record_exception_details=False,
            tracer=test_tracer,
        ):
            raise ValueError("sensitive detail")

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.status.status_code == StatusCode.ERROR
    assert span.status.description == "ValueError"
    assert _exception_messages(span) == []


def test_traced_span_records_exception_details_when_enabled(
    test_tracer: trace.Tracer,
    memory_exporter: InMemorySpanExporter,
) -> None:
    with pytest.raises(RuntimeError, match="verbose detail"):
        with traced_span(
            "test.span",
            record_exception_details=True,
            tracer=test_tracer,
        ):
            raise RuntimeError("verbose detail")

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.status.status_code == StatusCode.ERROR
    assert span.status.description == "verbose detail"
    assert "verbose detail" in _exception_messages(span)


def test_traced_span_attaches_attributes(
    test_tracer: trace.Tracer,
    memory_exporter: InMemorySpanExporter,
) -> None:
    with traced_span(
        "test.span",
        attributes={"foo": 1},
        tracer=test_tracer,
    ):
        pass

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    attributes = spans[0].attributes or {}
    assert attributes["foo"] == 1


def test_telemetry_config_defaults() -> None:
    config = TelemetryConfig()
    assert config.record_sensitive_data is False
    assert config.log_trace_context is True


def test_telemetry_config_traced_span_uses_record_sensitive_data(
    test_tracer: trace.Tracer,
    memory_exporter: InMemorySpanExporter,
) -> None:
    config = TelemetryConfig(record_sensitive_data=True)

    with pytest.raises(RuntimeError, match="boom"):
        with config.traced_span("config.span", tracer=test_tracer):
            raise RuntimeError("boom")

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.status.status_code == StatusCode.ERROR
    assert span.status.description == "boom"
    assert "boom" in _exception_messages(span)


def test_telemetry_config_traced_span_redacts_by_default(
    test_tracer: trace.Tracer,
    memory_exporter: InMemorySpanExporter,
) -> None:
    config = TelemetryConfig()

    with pytest.raises(ValueError):
        with config.traced_span("config.span", tracer=test_tracer):
            raise ValueError("sensitive detail")

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.status.status_code == StatusCode.ERROR
    assert span.status.description == "ValueError"
    assert _exception_messages(span) == []


def test_get_telemetry_config_returns_disabled_when_no_server() -> None:
    with patch(
        "north_mcp_python_sdk.telemetry.get_server",
        side_effect=RuntimeError("No FastMCP server instance in context"),
    ):
        config = get_telemetry_config()
    assert config.record_sensitive_data is False
    assert config.log_trace_context is False


def test_get_telemetry_config_returns_active_server_config() -> None:
    server = NorthMCPServer(
        name="t-active",
        telemetry=TelemetryConfig(record_sensitive_data=True),
    )
    with patch(
        "north_mcp_python_sdk.telemetry.get_server",
        return_value=server,
    ):
        config = get_telemetry_config()
    assert config is server.telemetry
    assert config.record_sensitive_data is True


def test_get_telemetry_config_returns_disabled_for_non_north_server() -> None:
    class _FakeFastMCP:
        pass

    with patch(
        "north_mcp_python_sdk.telemetry.get_server",
        return_value=_FakeFastMCP(),
    ):
        config = get_telemetry_config()
    assert config.record_sensitive_data is False
    assert config.log_trace_context is False


def test_traced_span_resolves_exception_details_from_active_server(
    test_tracer: trace.Tracer,
    memory_exporter: InMemorySpanExporter,
) -> None:
    server = NorthMCPServer(
        name="t-auto-record",
        telemetry=TelemetryConfig(record_sensitive_data=True),
    )

    with patch(
        "north_mcp_python_sdk.telemetry.get_server",
        return_value=server,
    ):
        with pytest.raises(RuntimeError, match="boom"):
            with traced_span("auto.span", tracer=test_tracer):
                raise RuntimeError("boom")

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.status.description == "boom"
    assert "boom" in _exception_messages(span)


def test_traced_span_explicit_kwarg_overrides_active_server(
    test_tracer: trace.Tracer,
    memory_exporter: InMemorySpanExporter,
) -> None:
    server = NorthMCPServer(
        name="t-auto-override",
        telemetry=TelemetryConfig(record_sensitive_data=True),
    )

    with patch(
        "north_mcp_python_sdk.telemetry.get_server",
        return_value=server,
    ):
        with pytest.raises(RuntimeError, match="boom"):
            with traced_span(
                "auto.span",
                record_exception_details=False,
                tracer=test_tracer,
            ):
                raise RuntimeError("boom")

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.status.description == "RuntimeError"
    assert _exception_messages(span) == []


def test_trace_context_formatter_appends_ids(
    test_tracer: trace.Tracer,
) -> None:
    formatter = TraceContextFormatter("%(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello",
        args=(),
        exc_info=None,
    )

    assert formatter.format(record) == "hello"

    with test_tracer.start_as_current_span("test.span"):
        formatted = formatter.format(record)
    assert "trace_id=" in formatted
    assert "span_id=" in formatted
    assert "hello" in formatted


def test_north_server_skips_formatter_when_telemetry_not_opted_in() -> None:
    server = NorthMCPServer(name="t-default")
    formatters = [
        h.formatter for h in server._logger.handlers if h.formatter is not None
    ]
    assert not any(isinstance(f, TraceContextFormatter) for f in formatters)


def test_north_server_attaches_formatter_when_telemetry_opted_in() -> None:
    server = NorthMCPServer(name="t-opt-in", telemetry=TelemetryConfig())
    formatters = [
        h.formatter for h in server._logger.handlers if h.formatter is not None
    ]
    assert any(isinstance(f, TraceContextFormatter) for f in formatters)


def test_north_server_skips_formatter_when_log_trace_context_off() -> None:
    server = NorthMCPServer(
        name="t-no-trace-log",
        telemetry=TelemetryConfig(log_trace_context=False),
    )
    formatters = [
        h.formatter for h in server._logger.handlers if h.formatter is not None
    ]
    assert not any(isinstance(f, TraceContextFormatter) for f in formatters)


def test_north_server_exposes_telemetry_config() -> None:
    config = TelemetryConfig(record_sensitive_data=True)
    server = NorthMCPServer(name="t-cfg", telemetry=config)
    assert server.telemetry is config
    assert server.telemetry.record_sensitive_data is True


@pytest.mark.asyncio
async def test_depends_injects_active_telemetry_config() -> None:
    server = NorthMCPServer(
        name="t-depends-opt-in",
        telemetry=TelemetryConfig(record_sensitive_data=True),
    )

    received: list[TelemetryConfig] = []

    @server.tool()
    async def my_tool(
        telemetry: TelemetryConfig = Depends(get_telemetry_config),
    ) -> str:
        received.append(telemetry)
        return "ok"

    await server.call_tool("my_tool", {})

    assert len(received) == 1
    assert received[0] is server.telemetry
    assert received[0].record_sensitive_data is True


@pytest.mark.asyncio
async def test_depends_injects_disabled_config_when_not_opted_in() -> None:
    server = NorthMCPServer(name="t-depends-off")

    received: list[TelemetryConfig] = []

    @server.tool()
    async def my_tool(
        telemetry: TelemetryConfig = Depends(get_telemetry_config),
    ) -> str:
        received.append(telemetry)
        return "ok"

    await server.call_tool("my_tool", {})

    assert len(received) == 1
    assert received[0].record_sensitive_data is False
    assert received[0].log_trace_context is False
