"""
North MCP server demonstrating OpenTelemetry with the SDK.

Setup (three steps):

1. Register a ``TracerProvider`` with exporters *before* importing
   ``NorthMCPServer`` (this file's ``_configure_tracing()``).
2. Construct ``NorthMCPServer`` with a :class:`TelemetryConfig`. Passing
   any config is the opt-in signal for the SDK's telemetry hooks; leaving
   ``telemetry=None`` leaves the server logger untouched. When
   ``log_trace_context`` is enabled (the default for an opted-in config)
   the server logger annotates log lines with the current ``trace_id``
   and ``span_id``.
3. Use ``mcp.telemetry.traced_span`` inside tools for custom spans nested
   under FastMCP's per-tool spans. The span automatically honours
   ``record_sensitive_data``.

Run from this directory::

    uv sync
    uv run python main.py

Set ``OTEL_EXPORTER_OTLP_ENDPOINT`` (default ``http://localhost:4317``) to send
traces to a collector. For broader auto-instrumentation, see FastMCP telemetry:
https://gofastmcp.com/servers/telemetry
"""

from __future__ import annotations

import asyncio
import os


def _configure_tracing() -> None:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://localhost:4317",
    )
    service_name = os.environ.get(
        "OTEL_SERVICE_NAME",
        "north-mcp-telemetry-demo",
    )
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)),
    )
    trace.set_tracer_provider(provider)


def main() -> None:
    _configure_tracing()

    from north_mcp_python_sdk import (
        Depends,
        NorthMCPServer,
        TelemetryConfig,
        get_telemetry_config,
    )

    mcp = NorthMCPServer(
        "Telemetry Demo",
        telemetry=TelemetryConfig(
            record_sensitive_data=False,
            log_trace_context=True,
        ),
    )

    @mcp.tool()
    async def demo_traced_pipeline(
        payload: str,
        telemetry: TelemetryConfig = Depends(get_telemetry_config),
    ) -> str:
        """Run a small pipeline: one custom span, then two sequential sub-spans.

        Demonstrates the FastAPI-style DI pattern: declaring
        ``telemetry: TelemetryConfig = Depends(get_telemetry_config)`` lets
        FastMCP inject the active server's config as a parameter, so tools
        do not need a reference to ``mcp`` at all.

        For tools that prefer not to expose the config in their signature,
        ``get_telemetry_config()`` and ``traced_span`` can be imported and
        called directly — they resolve the same active config via
        FastMCP's ``get_server`` dependency.
        """
        with telemetry.traced_span(
            "demo.pipeline",
            attributes={"payload.length": len(payload)},
        ) as span:
            if telemetry.record_sensitive_data:
                span.add_event("demo.payload", {"payload": payload})

            with telemetry.traced_span("demo.pipeline.validate"):
                await asyncio.sleep(0.03)
                normalized = payload.strip().lower()

            with telemetry.traced_span(
                "demo.pipeline.format",
                attributes={"normalized.length": len(normalized)},
            ):
                await asyncio.sleep(0.05)
                result = f"ok:{normalized}"

        return result

    port = int(os.environ.get("PORT", "5222"))
    mcp.run(transport="streamable-http", host="localhost", port=port)


if __name__ == "__main__":
    main()
