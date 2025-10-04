"""Integration tests for metrics HTTP endpoint."""

import asyncio
import time

import httpx
import pytest

from gobbler_mcp.metrics import conversion_total, track_conversion
from gobbler_mcp.metrics_server import MetricsServer


@pytest.fixture
async def metrics_server():
    """Create and start a metrics server for testing."""
    server = MetricsServer(host="127.0.0.1", port=9099)  # Use different port for tests
    server.start()

    # Wait for server to be ready
    await asyncio.sleep(0.5)

    yield server

    # Cleanup
    await server.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_metrics_endpoint_responds(metrics_server):
    """Test that /metrics endpoint is accessible."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:9099/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_endpoint_responds(metrics_server):
    """Test that /health endpoint is accessible."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:9099/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "gobbler-mcp"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_metrics_contain_application_info(metrics_server):
    """Test that metrics include application info."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:9099/metrics")
        text = response.text

        assert "gobbler_app_info" in text
        assert "version" in text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_metrics_updated_after_conversion(metrics_server):
    """Test that metrics are updated after conversions."""
    # Perform a tracked conversion
    with track_conversion("test_integration"):
        time.sleep(0.1)  # Simulate work

    # Give metrics time to update
    await asyncio.sleep(0.1)

    # Fetch metrics
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:9099/metrics")
        text = response.text

        # Verify conversion metrics are present
        assert "gobbler_conversions_total" in text
        assert 'converter_type="test_integration"' in text
        assert "gobbler_conversion_duration_seconds" in text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_metrics_include_resource_metrics(metrics_server):
    """Test that metrics include system resource metrics."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:9099/metrics")
        text = response.text

        # Verify resource metrics are present
        assert "gobbler_cpu_usage_percent" in text
        assert "gobbler_memory_usage_bytes" in text
        assert "gobbler_disk_usage_percent" in text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_server_can_be_stopped_and_restarted(metrics_server):
    """Test that server can be stopped and restarted."""
    # Server is already running from fixture

    # Verify it's running
    assert metrics_server.is_running()

    # Stop it
    await metrics_server.stop()
    await asyncio.sleep(0.2)

    # Verify it's stopped
    assert not metrics_server.is_running()

    # Start it again
    metrics_server.start()
    await asyncio.sleep(0.5)

    # Verify it's running again
    assert metrics_server.is_running()

    # Verify endpoint still works
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:9099/health")
        assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_metric_requests(metrics_server):
    """Test handling concurrent requests to metrics endpoint."""
    async with httpx.AsyncClient() as client:
        # Make multiple concurrent requests
        tasks = [
            client.get("http://127.0.0.1:9099/metrics") for _ in range(10)
        ]
        responses = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r.status_code == 200 for r in responses)
        assert all("gobbler_app_info" in r.text for r in responses)
