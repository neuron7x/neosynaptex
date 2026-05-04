# MLSDM Observability Module

JSON structured logging utilities for the MLSDM Governed Cognitive Memory architecture.

## Overview

The observability module provides a comprehensive logging solution designed specifically for cognitive architecture systems. It implements structured JSON logging with automatic rotation, multiple log levels, and thread-safe operation.

## Features

### Core Capabilities

- **JSON Structured Logs**: Every log entry is formatted as JSON with consistent fields
- **Multiple Log Levels**: DEBUG, INFO, WARNING, ERROR
- **Dual Log Rotation**:
  - Size-based rotation (RotatingFileHandler)
  - Time-based rotation (TimedRotatingFileHandler)
- **Thread-Safe**: Fully thread-safe for concurrent logging
- **Correlation IDs**: Automatic generation for request tracing
- **Flexible Metrics**: Attach custom metrics to any log entry

### Cognitive System Events

Pre-built convenience methods for common cognitive system events:

- **Moral Governance**: `moral_rejected`, `moral_accepted`
- **Rhythm Management**: `sleep_phase_entered`, `wake_phase_entered`
- **Memory Management**: `memory_full`, `memory_store`
- **Performance**: `processing_time_exceeded`
- **Lifecycle**: `system_startup`, `system_shutdown`

## Quick Start

### Basic Usage

```python
from mlsdm.observability import EventType, get_observability_logger

# Get logger instance
logger = get_observability_logger(
    logger_name="mlsdm_app",
    log_dir="/var/log/mlsdm",
    max_bytes=10 * 1024 * 1024,  # 10 MB
    backup_count=5,
    max_age_days=7,
)

# Log a moral rejection event
logger.log_moral_rejected(
    moral_value=0.3,
    threshold=0.5
)

# Log a memory full warning
logger.log_memory_full(
    current_size=20000,
    capacity=20000,
    memory_mb=512.5
)

# Log with custom metrics
logger.info(
    EventType.EVENT_PROCESSED,
    "Processed cognitive event",
    metrics={
        "processing_time_ms": 25.5,
        "vector_dim": 384,
    }
)
```

### Configuration Options

```python
logger = get_observability_logger(
    logger_name="mlsdm_app",          # Logger name
    log_dir="/var/log/mlsdm",         # Log directory (None = current dir)
    log_file="app.log",               # Log filename
    max_bytes=10 * 1024 * 1024,       # Max size before rotation (10MB)
    backup_count=5,                   # Number of backup files
    max_age_days=7,                   # Max age for time-based rotation
    console_output=True,              # Also log to console
    min_level=logging.INFO,           # Minimum log level
)
```

## Log Format

Each log entry is a JSON object with the following structure:

```json
{
  "timestamp": "2025-11-21T16:59:04.990869+00:00",
  "timestamp_unix": 1763744344.9908721,
  "level": "WARNING",
  "logger": "mlsdm_app",
  "event_type": "moral_rejected",
  "correlation_id": "4132d8d5-fdf8-4c68-9726-1d74d3bc069e",
  "message": "Input rejected due to low moral value: 0.300 < 0.500",
  "metrics": {
    "moral_value": 0.3,
    "threshold": 0.5
  }
}
```

### Fields

- **timestamp**: ISO 8601 format with timezone (UTC)
- **timestamp_unix**: Unix timestamp (seconds since epoch)
- **level**: Log level (DEBUG, INFO, WARNING, ERROR)
- **logger**: Logger name
- **event_type**: Type of event (from EventType enum)
- **correlation_id**: Unique ID for request tracking
- **message**: Human-readable message
- **metrics**: Event-specific metrics (optional)

## Event Types

### Moral Governance Events

```python
logger.log_moral_rejected(moral_value=0.3, threshold=0.5)
logger.log_moral_accepted(moral_value=0.8, threshold=0.5)
```

### Rhythm/Phase Events

```python
logger.log_sleep_phase_entered(previous_phase="wake")
logger.log_wake_phase_entered(previous_phase="sleep")
```

### Memory Events

```python
logger.log_memory_full(
    current_size=20000,
    capacity=20000,
    memory_mb=512.5
)

logger.log_memory_store(
    vector_dim=384,
    memory_size=1000
)
```

### System Events

```python
logger.log_system_startup(
    version="1.0.0",
    config={"dim": 384, "capacity": 20000}
)

logger.log_system_shutdown(reason="normal")
```

### Performance Events

```python
logger.log_processing_time_exceeded(
    processing_time_ms=1500.0,
    threshold_ms=1000.0
)
```

## Advanced Usage

### Custom Events with Metrics

```python
# Log with custom metrics
correlation_id = logger.info(
    EventType.STATE_CHANGE,
    "System state updated",
    metrics={
        "old_state": "initializing",
        "new_state": "active",
        "duration_ms": 1250.5,
    }
)
```

### Error Logging with Exception Info

```python
try:
    # Some operation
    raise ValueError("Invalid configuration")
except ValueError:
    logger.error(
        EventType.SYSTEM_ERROR,
        "Configuration error",
        exc_info=True,  # Include exception traceback
        metrics={"config_file": "/etc/mlsdm/config.yaml"}
    )
```

### Correlation ID Tracking

```python
# Generate or receive correlation ID
correlation_id = "request-123"

# Use same correlation ID across related log entries
logger.info(
    EventType.EVENT_PROCESSED,
    "Started processing",
    correlation_id=correlation_id
)

# ... processing ...

logger.info(
    EventType.EVENT_PROCESSED,
    "Completed processing",
    correlation_id=correlation_id
)
```

## Log Rotation

The logger implements dual rotation strategies:

### Size-Based Rotation

- Automatically rotates when log file reaches `max_bytes`
- Keeps `backup_count` backup files
- Backup files named: `app.log.1`, `app.log.2`, etc.

### Time-Based Rotation

- Automatically rotates at midnight each day
- Keeps logs for `max_age_days`
- Backup files named: `app_daily.log.2025-11-21`

## Thread Safety

The logger is fully thread-safe:

- **Internal locking**: All log operations are protected with locks
- **Singleton pattern**: `get_observability_logger()` uses double-checked locking
- **Concurrent logging**: Multiple threads can safely log simultaneously

## Testing

The module includes comprehensive unit tests (40 tests):

```bash
pytest tests/unit/test_observability_logger.py -v
```

Test coverage includes:
- Basic logging functionality
- All log levels
- Event types
- Metrics handling
- Log rotation
- Thread safety
- Edge cases (zero capacity, None metrics, etc.)
- JSON formatting
- Correlation ID handling

## Best Practices

1. **Use Correlation IDs**: Track related events with correlation IDs
2. **Include Metrics**: Add relevant metrics for debugging and analysis
3. **Choose Appropriate Levels**:
   - DEBUG: Detailed diagnostic information
   - INFO: Normal operations and events
   - WARNING: Potentially problematic situations
   - ERROR: Error conditions that need attention

4. **Configure Rotation**: Set appropriate size and age limits for your environment
5. **Monitor Log Files**: Set up log aggregation/monitoring for production

## Example

See `examples/observability_logger_example.py` for a complete working example.

## Architecture Notes

This logger is designed following Principal System Architect / Principal Engineer best practices:

- **Separation of Concerns**: Dedicated module for observability
- **Type Safety**: Full mypy --strict compliance
- **Production-Ready**: Comprehensive error handling and edge case protection
- **Extensible**: Easy to add new event types
- **Observable**: Structured logs for easy parsing and analysis
- **Performant**: Minimal overhead with efficient locking

## License

MIT License - See repository root for full license.
