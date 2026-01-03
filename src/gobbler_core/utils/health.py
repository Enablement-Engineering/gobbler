"""Health check utilities for containerized services."""

import logging

import httpx

logger = logging.getLogger(__name__)


class ServiceHealth:
    """Service health checker."""

    def __init__(self, timeout: float = 5.0) -> None:
        """Initialize health checker.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ServiceHealth":
        """Enter async context manager."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        """Exit async context manager."""
        if self._client:
            await self._client.aclose()

    async def check_service(self, service_url: str, service_name: str) -> bool:
        """Check if a service is available.

        Args:
            service_url: Base URL of service
            service_name: Name of service for logging

        Returns:
            True if service is healthy, False otherwise
        """
        if not self._client:
            msg = "Health checker not initialized. Use as context manager."
            raise RuntimeError(msg)

        health_url = f"{service_url}/health"
        http_ok = 200
        try:
            response = await self._client.get(health_url)
            is_healthy = response.status_code == http_ok
            if is_healthy:
                logger.debug("%s service is healthy", service_name)
            else:
                logger.warning("%s service returned status %s", service_name, response.status_code)
        except httpx.ConnectError:
            logger.warning("%s service is not reachable at %s", service_name, service_url)
            return False
        except httpx.TimeoutException:
            logger.warning("%s service health check timed out", service_name)
            return False
        except Exception:
            logger.exception("Unexpected error checking %s health", service_name)
            return False
        else:
            return is_healthy

    async def check_all_services(self, service_urls: dict[str, str]) -> dict[str, bool]:
        """Check health of all services.

        Args:
            service_urls: Dictionary mapping service names to URLs

        Returns:
            Dictionary mapping service names to health status
        """
        results = {}
        for service_name, service_url in service_urls.items():
            results[service_name] = await self.check_service(service_url, service_name)
        return results


def get_service_unavailable_error(service_name: str) -> str:
    """Get formatted error message for unavailable service.

    Args:
        service_name: Name of the service

    Returns:
        Error message with instructions
    """
    service_lower = service_name.lower()
    return (
        f"{service_name} service unavailable. The service may not be running. "
        f"Start with: docker-compose up -d {service_lower}"
    )
