"""Telemetry helpers that nest under FastMCP tool spans.

Configure a ``TracerProvider`` (and exporters) in your server entrypoint before
importing ``NorthMCPServer``. Use ``traced_span`` for custom spans and
``TraceContextFormatter`` (attached to the North server logger automatically)
for trace/span IDs in log lines. For full auto-instrumentation, use the
``opentelemetry-instrument`` CLI per FastMCP docs instead of SDK env flags.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from fastmcp.telemetry import get_tracer
from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode, Tracer
from opentelemetry.util.types import AttributeValue


@contextmanager
def traced_span(
    name: str,
    *,
    verbose: bool = False,
    attributes: Mapping[str, AttributeValue] | None = None,
    tracer: Tracer | None = None,
) -> Iterator[Span]:
    """Open a span with privacy-aware error recording."""
    t = tracer or get_tracer()
    with t.start_as_current_span(
        name,
        record_exception=False,
        set_status_on_exception=False,
        attributes=attributes,
    ) as span:
        try:
            yield span
        except BaseException as exc:
            if verbose:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
            else:
                span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            raise


class TraceContextFormatter(logging.Formatter):
    """Append trace/span IDs to log records when a recording span is current."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        try:
            ctx = trace.get_current_span().get_span_context()
            if ctx.is_valid:
                return (
                    f"{base} [trace_id={ctx.trace_id:032x} "
                    f"span_id={ctx.span_id:016x}]"
                )
        except Exception:
            pass
        return base
