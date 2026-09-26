# Centralized Logging Module

A flexible, expandable logging system for the Pokémon API services.

## Usage

### Basic Usage

```python
from shared.logging import get_logger

logger = get_logger("my-service")
logger.info("Service started")
logger.warning("Something might be wrong")
logger.error("Something went wrong")
```

### Features

- **Colored console output** for better readability (green=INFO, yellow=WARNING, red=ERROR, cyan=DEBUG)
- **Centralized configuration** via environment variables
- **Service name prefix** in logs for easy identification in multi-container setups
- **Easily expandable** for structured logging, metrics, etc.

## Configuration

### Environment Variables

- `LOG_LEVEL` - Set the logging level (default: `INFO`)
  - Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- `SERVICE_NAME` - Name of the service (default: `pokemon-api`)
  - Used as prefix in all log messages

### Examples

```bash
# Run with DEBUG logging
LOG_LEVEL=DEBUG SERVICE_NAME=classifier python classifier_worker.py

# Run with ERROR level only
LOG_LEVEL=ERROR SERVICE_NAME=enhancement python main.py
```

## Log Levels

- `DEBUG` (36) - Detailed diagnostic information
- `INFO` (32) - General informational messages
- `WARNING` (33) - Warning messages (recoverable issues)
- `ERROR` (31) - Error messages (serious issues)
- `CRITICAL` (35) - Critical errors (system failures)

## Expanding the Logger

To add features like structured logging, file output, or metrics:

1. Edit `shared/logging/__init__.py`
2. Add new functions or classes (e.g., `get_json_logger()`, `log_metric()`)
3. Import and use in services

Example extensions:

```python
# Add JSON structured logging
def get_json_logger(name):
    # Returns a logger that outputs JSON

# Add metrics tracking
def log_metric(name, value, tags=None):
    # Track metrics to an external system

# Add contextual logging
class ContextualLogger:
    def __init__(self, logger, context):
        self.logger = logger
        self.context = context
    
    def info(self, msg):
        self.logger.info(f"{self.context}: {msg}")
```
