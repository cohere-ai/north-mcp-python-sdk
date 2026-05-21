"""
North MCP server demonstrating OpenTelemetry with the SDK.

Setup (three steps):

1. Register a ``TracerProvider`` with exporters *before* importing
   ``NorthMCPServer`` (this file's ``_configure_tracing()``).
2. Construct ``NorthMCPServer`` — log lines on ``NorthMCP.*`` include trace/span
   IDs when a span is active (``TraceContextFormatter``).
3. Use ``traced_span`` inside tools for custom spans nested under FastMCP's
   per-tool spans.

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

    from north_mcp_python_sdk import NorthMCPServer, traced_span

    mcp = NorthMCPServer("Telemetry Demo")

    @mcp.tool()
    async def demo_traced_pipeline(payload: str) -> str:
        """Run a small pipeline: one custom span, then two sequential sub-spans."""
        with traced_span(
            "demo.pipeline",
            attributes={"payload.length": len(payload)},
        ):
            with traced_span("demo.pipeline.validate"):
                await asyncio.sleep(0.03)
                normalized = payload.strip().lower()

            with traced_span(
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
