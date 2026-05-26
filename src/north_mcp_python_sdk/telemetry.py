"""Telemetry helpers that nest under FastMCP tool spans.

Configure a ``TracerProvider`` (and exporters) in your server entrypoint
before importing ``NorthMCPServer``. Pass a :class:`TelemetryConfig` to the
server to opt into the SDK's telemetry behaviours
(:class:`TraceContextFormatter` on the ``NorthMCP.*`` logger and
exception-detail recording inside :func:`traced_span`).

Inside tools, use ``mcp.telemetry.traced_span`` when you have a reference
to the server, or import :func:`traced_span` and :func:`get_telemetry_config`
directly when you do not — both look up the active server's config via
FastMCP's :func:`fastmcp.server.dependencies.get_server`.

For full auto-instrumentation, use the ``opentelemetry-instrument`` CLI per
FastMCP docs.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass

from fastmcp.server.dependencies import get_server
from fastmcp.telemetry import get_tracer
from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode, Tracer
from opentelemetry.util.types import AttributeValue


@dataclass(frozen=True)
class TelemetryConfig:
    """Configuration for the North SDK's OpenTelemetry behaviours.

    Constructing a ``TelemetryConfig`` is the opt-in signal for the SDK's
    telemetry-side behaviours. It does **not** control whether spans are
    emitted — that is the user's :class:`opentelemetry.sdk.trace.TracerProvider`
    decision and FastMCP's own SERVER spans (``tools/call``,
    ``resources/read``, ``prompts/get``) flow regardless of whether this
    config was constructed.

    What this config actually controls:

    - ``record_sensitive_data`` — whether :func:`traced_span` writes full
      exception messages/stacks onto the span on error, and the policy that
      tool code can read to gate sensitive event payloads
      (``if config.record_sensitive_data: span.add_event(...)``).
    - ``log_trace_context`` — whether the SDK attaches
      :class:`TraceContextFormatter` to the ``NorthMCP.*`` logger so log
      lines pick up ``trace_id`` / ``span_id`` while a span is active.

    The dataclass defaults represent the opted-in baseline
    (``record_sensitive_data=False``, ``log_trace_context=True``). When
    ``telemetry=None`` is passed to ``NorthMCPServer`` (the default),
    both flags are ``False`` and the SDK leaves the server logger alone.
    """

    record_sensitive_data: bool = False
    log_trace_context: bool = True

    @contextmanager
    def traced_span(
        self,
        name: str,
        *,
        attributes: Mapping[str, AttributeValue] | None = None,
        tracer: Tracer | None = None,
    ) -> Iterator[Span]:
        """Open a span that respects this config's privacy settings."""
        with traced_span(
            name,
            record_exception_details=self.record_sensitive_data,
            attributes=attributes,
            tracer=tracer,
        ) as span:
            yield span


_TELEMETRY_DISABLED = TelemetryConfig(
    record_sensitive_data=False,
    log_trace_context=False,
)


def get_telemetry_config() -> TelemetryConfig:
    """Return the active ``NorthMCPServer``'s :class:`TelemetryConfig`.

    Looks up the running FastMCP server via
    :func:`fastmcp.server.dependencies.get_server` and returns its
    ``telemetry`` attribute when it is a :class:`TelemetryConfig`. Returns
    a private "telemetry not opted in" config (both flags ``False``) when:

    - no FastMCP server is active in the current context, or
    - the active server is a plain ``FastMCP`` (not ``NorthMCPServer``), or
    - the server has no ``telemetry`` attribute.

    This is the import-only counterpart to ``mcp.telemetry`` for tool code
    that does not hold a reference to the server.
    """
    try:
        server = get_server()
    except RuntimeError:
        return _TELEMETRY_DISABLED
    config = getattr(server, "telemetry", None)
    if isinstance(config, TelemetryConfig):
        return config
    return _TELEMETRY_DISABLED


@contextmanager
def traced_span(
    name: str,
    *,
    record_exception_details: bool | None = None,
    attributes: Mapping[str, AttributeValue] | None = None,
    tracer: Tracer | None = None,
) -> Iterator[Span]:
    """Open a span with privacy-aware error recording.

    When ``record_exception_details`` is ``False``, exception messages and
    stack traces are dropped — only the exception class name is written to
    the span status. When ``True``, the full exception message and stack
    are recorded on the span.

    If left as ``None`` (the default), the flag is resolved from the active
    ``NorthMCPServer``'s :class:`TelemetryConfig` via
    :func:`get_telemetry_config` — i.e. it follows
    ``config.record_sensitive_data``. Pass an explicit ``True``/``False`` to
    override the server's policy for this span.

    This kwarg only affects exception recording; it does not change
    attributes or events attached by the caller. The broader policy of
    whether tools may record sensitive payloads lives on
    :attr:`TelemetryConfig.record_sensitive_data`.
    """
    if record_exception_details is None:
        record_exception_details = get_telemetry_config().record_sensitive_data

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
            if record_exception_details:
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


__all__ = [
    "TelemetryConfig",
    "TraceContextFormatter",
    "get_telemetry_config",
    "get_tracer",
    "traced_span",
]
