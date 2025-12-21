"""Service health monitoring for Gobbler Daemon.

Provides non-blocking health checks with caching for Docker services
and relay status.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """Health status for a service."""

    healthy: bool
    message: str
    last_check: float
    response_time_ms: Optional[float] = None


class HealthMonitor:
    """
    Service health monitor with non-blocking checks and caching.

    Periodically checks the health of Docker services (Crawl4AI, Docling, Redis)
    and relay server, caching results to avoid blocking operations.
    """

    def __init__(
        self,
        check_interval: int = 60,
        timeout: float = 5.0,
        cache_ttl: int = 30,
    ) -> None:
        """
        Initialize health monitor.

        Args:
            check_interval: Seconds between health checks
            timeout: Request timeout in seconds
            cache_ttl: Cache time-to-live in seconds
        """
        self.check_interval = check_interval
        self.timeout = timeout
        self.cache_ttl = cache_ttl

        self._status_cache: Dict[str, HealthStatus] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    async def start(self, service_urls: Dict[str, str]) -> None:
        """
        Start the health monitor.

        Args:
            service_urls: Dictionary mapping service names to URLs
        """
        async with self._lock:
            if self._running:
                logger.warning("Health monitor already running")
                return

            self._running = True
            self.service_urls = service_urls
            self._client = httpx.AsyncClient(timeout=self.timeout)

            # Run initial health check
            await self._check_all_services()

            # Start background monitoring task
            self._task = asyncio.create_task(self._monitor_loop())

            logger.info(
                f"Health monitor started (interval: {self.check_interval}s, "
                f"cache TTL: {self.cache_ttl}s)"
            )

    async def stop(self) -> None:
        """Stop the health monitor."""
        async with self._lock:
            if not self._running:
                return

            self._running = False

            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                self._task = None

            if self._client:
                await self._client.aclose()
                self._client = None

            logger.info("Health monitor stopped")

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval)
                if self._running:
                    await self._check_all_services()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}", exc_info=True)

    async def _check_all_services(self) -> None:
        """Check health of all services."""
        tasks = []
        for service_name, service_url in self.service_urls.items():
            tasks.append(self._check_service(service_name, service_url))

        # Run all checks concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_service(self, service_name: str, service_url: str) -> None:
        """
        Check health of a single service.

        Args:
            service_name: Name of the service
            service_url: URL of the service
        """
        if not self._client:
            return

        start_time = time.time()

        try:
            # For Redis, use different health check
            if "redis://" in service_url:
                healthy = await self._check_redis(service_url)
                message = "Redis is available" if healthy else "Redis is unavailable"
            else:
                # HTTP health check
                health_url = f"{service_url}/health"
                response = await self._client.get(health_url)
                healthy = response.status_code == 200
                message = (
                    f"Service is healthy"
                    if healthy
                    else f"Status code: {response.status_code}"
                )

            response_time_ms = (time.time() - start_time) * 1000

            status = HealthStatus(
                healthy=healthy,
                message=message,
                last_check=time.time(),
                response_time_ms=response_time_ms,
            )

            async with self._lock:
                self._status_cache[service_name] = status

            if healthy:
                logger.debug(
                    f"{service_name} health check passed "
                    f"({response_time_ms:.0f}ms)"
                )
            else:
                logger.warning(f"{service_name} health check failed: {message}")

        except httpx.ConnectError:
            status = HealthStatus(
                healthy=False,
                message=f"Service not reachable at {service_url}",
                last_check=time.time(),
            )
            async with self._lock:
                self._status_cache[service_name] = status
            logger.warning(f"{service_name} is not reachable at {service_url}")

        except httpx.TimeoutException:
            status = HealthStatus(
                healthy=False,
                message="Health check timed out",
                last_check=time.time(),
            )
            async with self._lock:
                self._status_cache[service_name] = status
            logger.warning(f"{service_name} health check timed out")

        except Exception as e:
            status = HealthStatus(
                healthy=False,
                message=f"Error: {str(e)}",
                last_check=time.time(),
            )
            async with self._lock:
                self._status_cache[service_name] = status
            logger.error(f"Error checking {service_name} health: {e}")

    async def _check_redis(self, redis_url: str) -> bool:
        """
        Check Redis health.

        Args:
            redis_url: Redis URL

        Returns:
            True if Redis is available
        """
        try:
            import redis.asyncio as redis

            # Extract connection params from URL
            # Format: redis://host:port
            url_parts = redis_url.replace("redis://", "").split(":")
            host = url_parts[0]
            port = int(url_parts[1]) if len(url_parts) > 1 else 6379

            client = redis.Redis(
                host=host, port=port, socket_connect_timeout=self.timeout
            )
            await client.ping()
            await client.close()
            return True
        except Exception:
            return False

    async def get_status(self, service_name: str) -> Optional[HealthStatus]:
        """
        Get cached health status for a service.

        Args:
            service_name: Name of the service

        Returns:
            HealthStatus if available, None otherwise
        """
        async with self._lock:
            status = self._status_cache.get(service_name)

        # Check if cache is stale
        if status and (time.time() - status.last_check) > self.cache_ttl:
            # Trigger background refresh but return stale data
            asyncio.create_task(
                self._check_service(service_name, self.service_urls[service_name])
            )

        return status

    async def get_all_status(self) -> Dict[str, HealthStatus]:
        """
        Get cached health status for all services.

        Returns:
            Dictionary mapping service names to health status
        """
        async with self._lock:
            return self._status_cache.copy()

    async def is_healthy(self, service_name: str) -> bool:
        """
        Check if a service is healthy (non-blocking).

        Uses cached status. Returns False if status is not available
        or cache is stale.

        Args:
            service_name: Name of the service

        Returns:
            True if service is healthy
        """
        status = await self.get_status(service_name)
        if not status:
            return False

        # Check cache freshness
        cache_age = time.time() - status.last_check
        if cache_age > self.cache_ttl:
            return False

        return status.healthy

    async def wait_for_healthy(
        self, service_name: str, timeout: float = 30.0, poll_interval: float = 1.0
    ) -> bool:
        """
        Wait for a service to become healthy.

        Args:
            service_name: Name of the service
            timeout: Maximum time to wait in seconds
            poll_interval: How often to check in seconds

        Returns:
            True if service became healthy, False if timeout
        """
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            if await self.is_healthy(service_name):
                return True

            # Force a health check
            if service_name in self.service_urls:
                await self._check_service(
                    service_name, self.service_urls[service_name]
                )

            await asyncio.sleep(poll_interval)

        return False

    def get_status_summary(self) -> Dict[str, Dict[str, any]]:
        """
        Get a summary of all service health statuses (synchronous).

        Returns:
            Dictionary mapping service names to status info
        """
        summary = {}
        for service_name, status in self._status_cache.items():
            cache_age = time.time() - status.last_check
            summary[service_name] = {
                "healthy": status.healthy,
                "message": status.message,
                "response_time_ms": status.response_time_ms,
                "cache_age_seconds": int(cache_age),
                "stale": cache_age > self.cache_ttl,
            }
        return summary
