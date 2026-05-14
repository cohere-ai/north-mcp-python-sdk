"""
North MCP server demonstrating FastMCP OpenTelemetry integration.

FastMCP emits a span for each tool call. This example adds a parent custom span
with two sequential child spans inside the tool.

TracerProvider must be registered before importing NorthMCPServer (which imports
FastMCP). See: https://gofastmcp.com/servers/telemetry

Run from this directory::

    uv sync
    uv run python main.py

Point ``OTEL_EXPORTER_OTLP_ENDPOINT`` (default ``http://localhost:4317``) at an
OTLP collector or desktop viewer, or use ``opentelemetry-instrument`` per the
FastMCP telemetry docs.
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

    from fastmcp.telemetry import get_tracer

    from north_mcp_python_sdk import NorthMCPServer

    mcp = NorthMCPServer("Telemetry Demo")

    @mcp.tool()
    async def demo_traced_pipeline(payload: str) -> str:
        """Run a small pipeline: one custom span, then two sequential sub-spans."""
        tracer = get_tracer()

        with tracer.start_as_current_span("demo.pipeline") as pipeline:
            pipeline.set_attribute("payload.length", len(payload))

            with tracer.start_as_current_span("demo.pipeline.validate"):
                await asyncio.sleep(0.03)
                normalized = payload.strip().lower()

            with tracer.start_as_current_span("demo.pipeline.format") as fmt:
                fmt.set_attribute("normalized.length", len(normalized))
                await asyncio.sleep(0.03)
                result = f"ok:{normalized}"

        return result

    port = int(os.environ.get("PORT", "5222"))
    mcp.run(transport="streamable-http", host="localhost", port=port)


if __name__ == "__main__":
    main()
