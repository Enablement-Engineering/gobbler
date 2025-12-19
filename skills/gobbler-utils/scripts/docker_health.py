#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0"]
# ///
"""
Check health of Docker services used by Gobbler.

Usage:
    uv run docker_health.py crawl4ai    # Check Crawl4AI (port 11235)
    uv run docker_health.py docling     # Check Docling (port 5001)
    uv run docker_health.py all         # Check all services
"""

import argparse
import sys

import httpx

SERVICES = {
    "crawl4ai": {
        "url": "http://localhost:11235/health",
        "name": "Crawl4AI",
        "port": 11235,
    },
    "docling": {
        "url": "http://localhost:5001/health",
        "name": "Docling",
        "port": 5001,
    },
}


def check_service(service_key: str) -> tuple[bool, str]:
    """Check if a service is healthy."""
    service = SERVICES[service_key]
    try:
        response = httpx.get(service["url"], timeout=5.0)
        if response.status_code == 200:
            return True, f"{service['name']} is healthy on port {service['port']}"
        else:
            return False, f"{service['name']} returned status {response.status_code}"
    except httpx.ConnectError:
        return False, f"{service['name']} is not running on port {service['port']}"
    except httpx.TimeoutException:
        return False, f"{service['name']} timed out on port {service['port']}"
    except Exception as e:
        return False, f"{service['name']} error: {e}"


def main():
    parser = argparse.ArgumentParser(description="Check Docker service health")
    parser.add_argument(
        "service",
        choices=["crawl4ai", "docling", "all"],
        help="Service to check",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    if args.service == "all":
        services_to_check = list(SERVICES.keys())
    else:
        services_to_check = [args.service]

    results = {}
    all_healthy = True

    for service_key in services_to_check:
        healthy, message = check_service(service_key)
        results[service_key] = {"healthy": healthy, "message": message}
        if not healthy:
            all_healthy = False
        print(f"{'✓' if healthy else '✗'} {message}")

    if args.json:
        import json
        print(json.dumps(results, indent=2))

    sys.exit(0 if all_healthy else 1)


if __name__ == "__main__":
    main()
