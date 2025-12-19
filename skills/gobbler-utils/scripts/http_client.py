#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0", "tenacity>=8.0.0"]
# ///
"""
Retry-enabled HTTP client for Docker service calls.

Usage:
    uv run http_client.py GET http://localhost:5001/health
    uv run http_client.py POST http://localhost:11235/crawl --json '{"urls": ["https://example.com"]}'
    uv run http_client.py POST http://localhost:5001/v1/convert/file --file document.pdf --form "to_formats=md"
"""

import argparse
import json
import sys
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


def create_retry_client(retries: int = 3):
    """Create an httpx client with retry logic."""

    @retry(
        stop=stop_after_attempt(retries),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def request_with_retry(method: str, url: str, **kwargs) -> httpx.Response:
        with httpx.Client(timeout=60.0) as client:
            response = client.request(method, url, **kwargs)
            response.raise_for_status()
            return response

    return request_with_retry


def main():
    parser = argparse.ArgumentParser(description="HTTP client with retry")
    parser.add_argument("method", choices=["GET", "POST", "PUT", "DELETE"], help="HTTP method")
    parser.add_argument("url", help="Request URL")
    parser.add_argument("--json", dest="json_data", help="JSON body (as string)")
    parser.add_argument("--file", help="File to upload (multipart)")
    parser.add_argument("--form", action="append", help="Form field (key=value)")
    parser.add_argument("--header", action="append", help="Header (key:value)")
    parser.add_argument("--retries", type=int, default=3, help="Number of retries")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout in seconds")
    args = parser.parse_args()

    # Build request kwargs
    kwargs = {"timeout": args.timeout}

    # Headers
    if args.header:
        headers = {}
        for h in args.header:
            key, value = h.split(":", 1)
            headers[key.strip()] = value.strip()
        kwargs["headers"] = headers

    # JSON body
    if args.json_data:
        kwargs["json"] = json.loads(args.json_data)

    # File upload
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        files = {"files": (file_path.name, open(file_path, "rb"))}
        kwargs["files"] = files

    # Form data
    if args.form:
        data = {}
        for f in args.form:
            key, value = f.split("=", 1)
            data[key] = value
        kwargs["data"] = data

    # Make request with retry
    try:
        request_fn = create_retry_client(args.retries)
        response = request_fn(args.method, args.url, **kwargs)

        # Output response
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            print(json.dumps(response.json(), indent=2))
        else:
            print(response.text)

        sys.exit(0)
    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except httpx.ConnectError:
        print(f"Connection Error: Could not connect to {args.url}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
