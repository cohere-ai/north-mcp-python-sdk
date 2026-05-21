"""Tests for north_mcp_python_sdk.telemetry helpers."""

from __future__ import annotations

import logging

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import StatusCode
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from north_mcp_python_sdk import NorthMCPServer
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


def test_traced_span_redacts_when_not_verbose(
    test_tracer: trace.Tracer,
    memory_exporter: InMemorySpanExporter,
) -> None:
    with pytest.raises(ValueError, match="sensitive"):
        with traced_span("test.span", verbose=False, tracer=test_tracer):
            raise ValueError("sensitive detail")

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.status.status_code == StatusCode.ERROR
    assert span.status.description == "ValueError"
    assert _exception_messages(span) == []


def test_traced_span_records_when_verbose(
    test_tracer: trace.Tracer,
    memory_exporter: InMemorySpanExporter,
) -> None:
    with pytest.raises(RuntimeError, match="verbose detail"):
        with traced_span("test.span", verbose=True, tracer=test_tracer):
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
    assert spans[0].attributes["foo"] == 1


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


def test_north_server_attaches_formatter() -> None:
    server = NorthMCPServer(name="t")
    formatters = [
        h.formatter for h in server._logger.handlers if h.formatter is not None
    ]
    assert any(isinstance(f, TraceContextFormatter) for f in formatters)

    default_server = NorthMCPServer(name="t-default")
    default_formatters = [
        h.formatter
        for h in default_server._logger.handlers
        if h.formatter is not None
    ]
    assert any(
        isinstance(f, TraceContextFormatter) for f in default_formatters
    )
