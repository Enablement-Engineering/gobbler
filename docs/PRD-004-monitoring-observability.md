# PRD-004: Monitoring and Observability

## Overview
**Epic**: Production Readiness & Operations
**Phase**: 3 - Infrastructure & DevOps
**Estimated Effort**: 5-6 days
**Dependencies**: None - adds monitoring layer to existing system
**Parallel**: ✅ Can be implemented alongside other PRDs

## Problem Statement
Gobbler MCP currently lacks comprehensive monitoring and observability, making it difficult to:
- Track system performance and resource usage
- Identify bottlenecks in conversion pipelines
- Debug issues in production environments
- Monitor queue health and worker status
- Track API usage and costs
- Alert on failures or degraded performance
- Understand user behavior and tool usage patterns

Production deployments need visibility into system health, performance metrics, error rates, and operational characteristics.

**Operational Pain Points:**
- No visibility into conversion success rates
- Can't track Whisper model performance across files
- Unknown queue backlogs and processing times
- No alerts when services fail
- Difficult to debug intermittent issues
- No cost tracking for external services

## Success Criteria
- [ ] Structured logging with appropriate log levels
- [ ] Prometheus metrics exposed via HTTP endpoint
- [ ] Performance tracking for all converters
- [ ] Queue metrics (depth, processing time, failures)
- [ ] Service health monitoring (Crawl4AI, Docling, Redis)
- [ ] Error tracking with context
- [ ] Resource usage metrics (CPU, memory, disk)
- [ ] Grafana dashboard templates provided
- [ ] Optional integration with observability platforms (DataDog, New Relic)

## Technical Requirements

### 1. Structured Logging

Replace basic logging with structured JSON logs:

```python
# src/gobbler_mcp/logging_config.py
import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict

class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)

def setup_logging(level: str = "INFO", format: str = "json"):
    """
    Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: 'json' for structured logging, 'text' for human-readable
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handler
    handler = logging.StreamHandler(sys.stderr)

    if format == "json":
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )

    root_logger.addHandler(handler)

# Usage in converters
import logging
logger = logging.getLogger(__name__)

# Log with extra fields
def log_conversion_start(converter_type: str, source: str):
    logger.info(
        "Conversion started",
        extra={
            "extra_fields": {
                "converter_type": converter_type,
                "source": source,
                "event_type": "conversion_start",
            }
        }
    )
```

### 2. Prometheus Metrics

Add metrics collection and HTTP endpoint:

```python
# src/gobbler_mcp/metrics.py
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from typing import Dict
import psutil
import time

# Create registry
registry = CollectorRegistry()

# Application info
app_info = Info(
    'gobbler_app',
    'Gobbler MCP Server Information',
    registry=registry
)
app_info.info({
    'version': '0.1.0',
    'python_version': '3.11',
})

# Conversion metrics
conversion_total = Counter(
    'gobbler_conversions_total',
    'Total number of conversions attempted',
    ['converter_type', 'status'],  # labels
    registry=registry
)

conversion_duration = Histogram(
    'gobbler_conversion_duration_seconds',
    'Time spent on conversions',
    ['converter_type'],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120, 300],
    registry=registry
)

conversion_size = Histogram(
    'gobbler_conversion_size_bytes',
    'Size of content converted',
    ['converter_type'],
    buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600],
    registry=registry
)

# Queue metrics
queue_depth = Gauge(
    'gobbler_queue_depth',
    'Number of jobs in queue',
    ['queue_name'],
    registry=registry
)

queue_processing_time = Histogram(
    'gobbler_queue_processing_seconds',
    'Time spent processing queued jobs',
    ['queue_name', 'job_type'],
    registry=registry
)

# Service health metrics
service_up = Gauge(
    'gobbler_service_up',
    'Service health status (1=up, 0=down)',
    ['service_name'],
    registry=registry
)

service_response_time = Histogram(
    'gobbler_service_response_seconds',
    'Service response time',
    ['service_name'],
    buckets=[0.1, 0.5, 1, 2, 5, 10],
    registry=registry
)

# Worker metrics
worker_active = Gauge(
    'gobbler_workers_active',
    'Number of active workers',
    registry=registry
)

worker_idle_time = Histogram(
    'gobbler_worker_idle_seconds',
    'Time workers spend idle',
    buckets=[1, 5, 10, 30, 60, 300],
    registry=registry
)

# Resource metrics
cpu_usage = Gauge(
    'gobbler_cpu_usage_percent',
    'CPU usage percentage',
    registry=registry
)

memory_usage = Gauge(
    'gobbler_memory_usage_bytes',
    'Memory usage in bytes',
    registry=registry
)

disk_usage = Gauge(
    'gobbler_disk_usage_percent',
    'Disk usage percentage',
    ['mount_point'],
    registry=registry
)

# Error tracking
errors_total = Counter(
    'gobbler_errors_total',
    'Total errors encountered',
    ['error_type', 'converter_type'],
    registry=registry
)

# Helper functions
def track_conversion(converter_type: str):
    """Context manager for tracking conversions"""
    class ConversionTracker:
        def __init__(self, converter_type: str):
            self.converter_type = converter_type
            self.start_time = None

        def __enter__(self):
            self.start_time = time.time()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            duration = time.time() - self.start_time
            conversion_duration.labels(
                converter_type=self.converter_type
            ).observe(duration)

            if exc_type is None:
                conversion_total.labels(
                    converter_type=self.converter_type,
                    status='success'
                ).inc()
            else:
                conversion_total.labels(
                    converter_type=self.converter_type,
                    status='failure'
                ).inc()
                errors_total.labels(
                    error_type=exc_type.__name__,
                    converter_type=self.converter_type
                ).inc()

    return ConversionTracker(converter_type)

def update_resource_metrics():
    """Update system resource metrics"""
    cpu_usage.set(psutil.cpu_percent())
    memory = psutil.virtual_memory()
    memory_usage.set(memory.used)

    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disk_usage.labels(
                mount_point=partition.mountpoint
            ).set(usage.percent)
        except:
            pass

def update_queue_metrics():
    """Update queue depth metrics from Redis"""
    from .utils.queue import get_queue

    for queue_name in ['default', 'transcription', 'download']:
        try:
            queue = get_queue(queue_name)
            depth = len(queue)
            queue_depth.labels(queue_name=queue_name).set(depth)
        except:
            pass

# Metrics endpoint
def get_metrics() -> tuple[bytes, str]:
    """Get Prometheus metrics in text format"""
    # Update dynamic metrics
    update_resource_metrics()
    update_queue_metrics()

    return generate_latest(registry), CONTENT_TYPE_LATEST
```

### 3. Metrics HTTP Endpoint

Add metrics server to expose Prometheus endpoint:

```python
# src/gobbler_mcp/metrics_server.py
import asyncio
from aiohttp import web
import logging
from .metrics import get_metrics

logger = logging.getLogger(__name__)

async def metrics_handler(request: web.Request) -> web.Response:
    """Handle /metrics endpoint for Prometheus scraping"""
    metrics_data, content_type = get_metrics()
    return web.Response(body=metrics_data, content_type=content_type)

async def health_handler(request: web.Request) -> web.Response:
    """Handle /health endpoint for health checks"""
    # Could add more sophisticated health checks here
    return web.json_response({"status": "healthy"})

def create_metrics_app() -> web.Application:
    """Create aiohttp application for metrics server"""
    app = web.Application()
    app.router.add_get('/metrics', metrics_handler)
    app.router.add_get('/health', health_handler)
    return app

async def run_metrics_server(host: str = '0.0.0.0', port: int = 9090):
    """Run metrics HTTP server"""
    app = create_metrics_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info(f"Metrics server running on http://{host}:{port}")
    # Keep server running
    await asyncio.Event().wait()

# Start metrics server in background
def start_metrics_server_background(host: str = '0.0.0.0', port: int = 9090):
    """Start metrics server in background thread"""
    import threading

    def run_in_thread():
        asyncio.run(run_metrics_server(host, port))

    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()
    return thread
```

### 4. Instrument Converters

Add metrics tracking to all converters:

```python
# Example: src/gobbler_mcp/converters/youtube.py
from ..metrics import track_conversion, conversion_size
import logging

logger = logging.getLogger(__name__)

async def convert_youtube_to_markdown(
    video_url: str,
    include_timestamps: bool = False,
    language: str = "auto",
) -> Tuple[str, Dict]:
    """Convert YouTube video to markdown with metrics tracking"""

    with track_conversion('youtube'):
        logger.info(
            "Starting YouTube conversion",
            extra={
                "extra_fields": {
                    "video_url": video_url,
                    "language": language,
                    "include_timestamps": include_timestamps,
                }
            }
        )

        # Extract video ID
        video_id = extract_video_id(video_url)

        # ... existing conversion logic ...

        # Track size
        conversion_size.labels(
            converter_type='youtube'
        ).observe(len(markdown))

        logger.info(
            "YouTube conversion completed",
            extra={
                "extra_fields": {
                    "video_id": video_id,
                    "word_count": word_count,
                    "language": detected_language,
                }
            }
        )

        return markdown, metadata
```

### 5. Service Health Monitoring

Enhanced health checks with metrics:

```python
# src/gobbler_mcp/utils/health_monitor.py
import asyncio
import logging
from typing import Dict
import httpx
from ..config import get_config
from ..metrics import service_up, service_response_time
import time

logger = logging.getLogger(__name__)

class HealthMonitor:
    """Continuous health monitoring for external services"""

    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval
        self.config = get_config()
        self.running = False

    async def check_service(self, name: str, url: str) -> bool:
        """Check single service health"""
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{url}/health")
                healthy = response.status_code == 200

                # Record metrics
                response_time = time.time() - start_time
                service_response_time.labels(
                    service_name=name
                ).observe(response_time)

                service_up.labels(service_name=name).set(1 if healthy else 0)

                if not healthy:
                    logger.warning(
                        f"Service {name} unhealthy",
                        extra={
                            "extra_fields": {
                                "service_name": name,
                                "status_code": response.status_code,
                            }
                        }
                    )

                return healthy

        except Exception as e:
            service_up.labels(service_name=name).set(0)
            logger.error(
                f"Service {name} health check failed",
                extra={
                    "extra_fields": {
                        "service_name": name,
                        "error": str(e),
                    }
                }
            )
            return False

    async def monitor_loop(self):
        """Continuous monitoring loop"""
        self.running = True

        services = {
            'crawl4ai': self.config.get_service_url('crawl4ai'),
            'docling': self.config.get_service_url('docling'),
            'redis': f"http://{self.config.get('redis.host')}:{self.config.get('redis.port')}",
        }

        while self.running:
            for name, url in services.items():
                await self.check_service(name, url)

            await asyncio.sleep(self.check_interval)

    def start_background(self):
        """Start monitoring in background task"""
        asyncio.create_task(self.monitor_loop())

    def stop(self):
        """Stop monitoring"""
        self.running = False
```

### 6. Grafana Dashboard Template

```json
// grafana/dashboards/gobbler-overview.json
{
  "dashboard": {
    "title": "Gobbler MCP Overview",
    "panels": [
      {
        "title": "Conversion Rate",
        "targets": [
          {
            "expr": "rate(gobbler_conversions_total{status=\"success\"}[5m])"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Conversion Duration (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, gobbler_conversion_duration_seconds_bucket)"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Queue Depth",
        "targets": [
          {
            "expr": "gobbler_queue_depth"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Service Health",
        "targets": [
          {
            "expr": "gobbler_service_up"
          }
        ],
        "type": "stat"
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(gobbler_errors_total[5m])"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Memory Usage",
        "targets": [
          {
            "expr": "gobbler_memory_usage_bytes"
          }
        ],
        "type": "graph"
      }
    ]
  }
}
```

### 7. Configuration Updates

```yaml
# ~/.config/gobbler/config.yml
# Add monitoring section
monitoring:
  metrics_enabled: true
  metrics_port: 9090
  metrics_host: 0.0.0.0
  log_format: json  # or 'text'
  log_level: INFO   # DEBUG, INFO, WARNING, ERROR
  health_check_interval: 60  # seconds

# Optional: Integration with external platforms
observability:
  # DataDog
  datadog:
    enabled: false
    api_key: ${DATADOG_API_KEY}

  # Sentry
  sentry:
    enabled: false
    dsn: ${SENTRY_DSN}
```

## Acceptance Criteria

### 1. Structured Logging
- [ ] All log entries in JSON format
- [ ] Appropriate log levels used (DEBUG, INFO, WARNING, ERROR)
- [ ] Context included (converter type, source, duration)
- [ ] Exception tracking with stack traces
- [ ] Log correlation IDs for request tracking

### 2. Metrics Collection
- [ ] Conversion metrics (count, duration, size)
- [ ] Queue metrics (depth, processing time)
- [ ] Service health metrics
- [ ] Resource metrics (CPU, memory, disk)
- [ ] Error counts and types
- [ ] Worker status metrics

### 3. Metrics Endpoint
- [ ] HTTP endpoint on configurable port
- [ ] Prometheus-compatible format
- [ ] Health check endpoint
- [ ] Metrics update automatically
- [ ] No authentication required (internal network assumed)

### 4. Dashboard Templates
- [ ] Grafana dashboard JSON provided
- [ ] Key metrics visualized
- [ ] Alerting rules documented
- [ ] Dashboard import instructions

### 5. Performance
- [ ] Metrics collection adds <5ms overhead
- [ ] Logging doesn't block operations
- [ ] Resource metrics update efficiently
- [ ] No memory leaks in metric collectors

## Deliverables

### Files to Create
```
src/gobbler_mcp/
├── logging_config.py             # Structured logging setup
├── metrics.py                    # Prometheus metrics definitions
├── metrics_server.py             # HTTP metrics endpoint
└── utils/
    └── health_monitor.py         # Service health monitoring

grafana/
├── dashboards/
│   ├── gobbler-overview.json     # Main dashboard
│   ├── gobbler-conversions.json  # Conversion metrics
│   └── gobbler-queues.json       # Queue metrics
└── provisioning/
    ├── datasources.yml           # Prometheus datasource
    └── dashboards.yml            # Dashboard provisioning

docs/
└── monitoring/
    ├── metrics.md                # Metrics documentation
    ├── grafana-setup.md          # Grafana setup guide
    └── alerting.md               # Alert configuration

tests/
├── unit/
│   ├── test_metrics.py
│   └── test_logging.py
└── integration/
    └── test_metrics_endpoint.py

docker-compose.monitoring.yml     # Prometheus + Grafana stack
```

### Docker Compose for Monitoring Stack

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: gobbler-prometheus
    ports:
      - "9091:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: gobbler-grafana
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards
      - grafana-data:/var/lib/grafana
    restart: unless-stopped

volumes:
  prometheus-data:
  grafana-data:
```

### Prometheus Configuration

```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'gobbler'
    static_configs:
      - targets: ['host.docker.internal:9090']
        labels:
          environment: 'development'
          service: 'gobbler-mcp'
```

## Testing

```python
# tests/unit/test_metrics.py
import pytest
from gobbler_mcp.metrics import (
    conversion_total,
    track_conversion,
    get_metrics,
)

def test_track_conversion_success():
    """Test successful conversion tracking"""
    initial_count = conversion_total.labels(
        converter_type='test',
        status='success'
    )._value.get()

    with track_conversion('test'):
        pass  # Simulate successful conversion

    final_count = conversion_total.labels(
        converter_type='test',
        status='success'
    )._value.get()

    assert final_count == initial_count + 1

def test_track_conversion_failure():
    """Test failed conversion tracking"""
    initial_count = conversion_total.labels(
        converter_type='test',
        status='failure'
    )._value.get()

    with pytest.raises(ValueError):
        with track_conversion('test'):
            raise ValueError("Test error")

    final_count = conversion_total.labels(
        converter_type='test',
        status='failure'
    )._value.get()

    assert final_count == initial_count + 1

def test_metrics_endpoint():
    """Test metrics can be exported"""
    metrics_data, content_type = get_metrics()

    assert content_type == 'text/plain; version=0.0.4; charset=utf-8'
    assert b'gobbler_conversions_total' in metrics_data
```

## Usage Examples

### Starting with Monitoring

```bash
# Start monitoring stack
docker-compose -f docker-compose.monitoring.yml up -d

# Start Gobbler with metrics enabled
GOBBLER_METRICS_ENABLED=true uv run gobbler-mcp

# Access Grafana: http://localhost:3001
# Username: admin, Password: admin
```

### Querying Metrics

```bash
# View raw metrics
curl http://localhost:9090/metrics

# Check health
curl http://localhost:9090/health
```

## Definition of Done
- [ ] Structured logging implemented and working
- [ ] Prometheus metrics defined and collected
- [ ] Metrics HTTP endpoint functional
- [ ] Grafana dashboards created and tested
- [ ] Service health monitoring working
- [ ] Documentation complete
- [ ] Tests passing
- [ ] Performance overhead acceptable
- [ ] Docker Compose stack provided and tested

## References
- Prometheus Python client: https://github.com/prometheus/client_python
- Grafana dashboards: https://grafana.com/docs/grafana/latest/dashboards/
- Structured logging best practices: https://www.structlog.org/
- Python logging: https://docs.python.org/3/library/logging.html
