# Threading Utilities

Thread pool utilities for managed background task execution in AtomX.

## Overview

The `core.threading_utils` module provides a managed thread pool implementation built on Python's `concurrent.futures.ThreadPoolExecutor`. It offers better resource management, error handling, and integration with logging compared to using bare `threading.Thread`.

## Features

- **Resource Pooling**: Reuses worker threads instead of creating new ones
- **Task Tracking**: Track and manage tasks by name
- **Error Handling**: Automatic exception logging and propagation
- **Graceful Shutdown**: Clean thread pool shutdown with optional wait
- **Context Manager**: RAII-style resource management
- **Global Instance**: Shared thread pool for application-wide use

## Basic Usage

### Using a Local Thread Pool

```python
from core.threading_utils import ManagedThreadPool

# Create a thread pool
pool = ManagedThreadPool(max_workers=4, thread_name_prefix="MyWorker")

# Submit a task
def process_data(data):
    # Do some work
    return data * 2

future = pool.submit(process_data, 42)

# Get the result
result = future.result(timeout=5.0)  # result = 84

# Clean up
pool.shutdown(wait=True)
```

### Using as Context Manager

```python
from core.threading_utils import ManagedThreadPool

with ManagedThreadPool(max_workers=2) as pool:
    # Submit tasks
    future1 = pool.submit(lambda x: x * 2, 5)
    future2 = pool.submit(lambda x: x + 10, 5)

    # Get results
    result1 = future1.result()  # 10
    result2 = future2.result()  # 15

# Pool is automatically shutdown when exiting context
```

### Using Named Tasks for Tracking

```python
from core.threading_utils import ManagedThreadPool
import time

pool = ManagedThreadPool()

def long_running_task():
    time.sleep(2.0)
    return "done"

# Submit with a name
pool.submit(long_running_task, task_name="analysis")

# Check if still running
if pool.is_task_running("analysis"):
    print("Task is still running...")

# Wait for completion
result = pool.wait_for_task("analysis", timeout=5.0)

# Or cancel if needed
pool.cancel_task("analysis")

pool.shutdown()
```

### Using Global Thread Pool

For application-wide background tasks:

```python
from core.threading_utils import get_global_thread_pool, shutdown_global_thread_pool

# Get the global instance
pool = get_global_thread_pool(max_workers=4)

# Submit tasks from anywhere in your application
future = pool.submit(my_function, arg1, arg2)

# Shutdown at application exit
shutdown_global_thread_pool(wait=True)
```

### Using Temporary Thread Pool Context

For one-off operations:

```python
from core.threading_utils import thread_pool_context

with thread_pool_context(max_workers=2, thread_name_prefix="Temp") as pool:
    futures = [pool.submit(process_item, item) for item in items]
    results = [f.result() for f in futures]
```

## Integration with Logging

```python
import logging
from core.threading_utils import ManagedThreadPool

logger = logging.getLogger(__name__)

# Pass logger to get automatic task logging
pool = ManagedThreadPool(max_workers=4, logger=logger)

def my_task(x):
    return x * 2

# Task execution will be logged
future = pool.submit(my_task, 5, task_name="calculation")

# Exceptions are automatically logged
def failing_task():
    raise ValueError("Something went wrong")

future = pool.submit(failing_task, task_name="will_fail")
```

## Advanced Usage

### Submitting Multiple Tasks

```python
pool = ManagedThreadPool(max_workers=4)

items = [1, 2, 3, 4, 5]

# Submit all tasks
futures = [pool.submit(process_item, item) for item in items]

# Wait for all to complete
results = [future.result() for future in futures]

pool.shutdown()
```

### Handling Task Exceptions

```python
pool = ManagedThreadPool()

def risky_task():
    raise ValueError("Task failed")

future = pool.submit(risky_task)

try:
    result = future.result(timeout=1.0)
except ValueError as e:
    print(f"Task failed: {e}")

pool.shutdown()
```

### Graceful Shutdown

```python
pool = ManagedThreadPool()

# Submit long-running tasks
for i in range(10):
    pool.submit(long_task, i)

# Shutdown and wait for all tasks to complete
pool.shutdown(wait=True)

# Or cancel all running tasks immediately
pool.shutdown(wait=False)
```

## Migration from threading.Thread

### Before (using bare threads):

```python
import threading

def run_sequence():
    # Execute sequence steps
    pass

thread = threading.Thread(target=run_sequence)
thread.daemon = True
thread.start()
```

### After (using thread pool):

```python
from core.threading_utils import get_global_thread_pool

def run_sequence():
    # Execute sequence steps
    pass

pool = get_global_thread_pool()
future = pool.submit(run_sequence, task_name="sequence")

# Optionally wait for completion
result = future.result(timeout=30.0)
```

## Benefits Over threading.Thread

1. **Resource Efficiency**: Thread pools reuse worker threads
2. **Better Error Handling**: Exceptions are captured and can be logged
3. **Task Management**: Track, cancel, and wait for tasks by name
4. **Graceful Shutdown**: Clean cleanup of all background tasks
5. **Integration Ready**: Works with logging, monitoring, and debugging tools

## Best Practices

1. **Use Global Pool for App-Wide Tasks**: Share one pool across the application
2. **Use Local Pool for Isolated Work**: Create separate pools for independent subsystems
3. **Always Shutdown**: Use context managers or explicit shutdown calls
4. **Set Reasonable max_workers**: Typically 2-4x CPU cores for I/O bound tasks
5. **Handle Exceptions**: Always wrap `future.result()` in try-except
6. **Use Task Names**: Makes debugging and monitoring easier

## Examples in AtomX

### Example 1: Background Sequence Execution (Future Use)

```python
from core.threading_utils import get_global_thread_pool

class Sequencer:
    def __init__(self):
        self.pool = get_global_thread_pool()

    def start_sequence(self, steps):
        future = self.pool.submit(
            self._run_sequence,
            steps,
            task_name="sequence_execution"
        )
        return future

    def _run_sequence(self, steps):
        for step in steps:
            # Execute step
            pass
```

### Example 2: Parallel Instrument Initialization

```python
from core.threading_utils import thread_pool_context

def initialize_instruments_parallel():
    with thread_pool_context(max_workers=4) as pool:
        futures = []

        futures.append(pool.submit(init_power_supply, task_name="ps_init"))
        futures.append(pool.submit(init_oscilloscope, task_name="os_init"))
        futures.append(pool.submit(init_dc_load, task_name="load_init"))

        # Wait for all to complete
        results = [f.result() for f in futures]

        return all(success for success, _ in results)
```

### Example 3: Periodic Background Tasks

```python
from core.threading_utils import get_global_thread_pool
import time

def monitor_instruments():
    pool = get_global_thread_pool()

    def check_health():
        while True:
            # Check instrument health
            time.sleep(5.0)

    pool.submit(check_health, task_name="health_monitor")
```

## API Reference

### ManagedThreadPool

- `__init__(max_workers, thread_name_prefix, logger)`: Create thread pool
- `submit(fn, *args, task_name, **kwargs)`: Submit task for execution
- `cancel_task(task_name)`: Cancel a tracked task
- `is_task_running(task_name)`: Check if task is running
- `wait_for_task(task_name, timeout)`: Wait for task completion
- `shutdown(wait, timeout)`: Shutdown the thread pool

### Global Functions

- `get_global_thread_pool(max_workers, logger)`: Get global pool instance
- `shutdown_global_thread_pool(wait)`: Shutdown global pool
- `thread_pool_context(max_workers, thread_name_prefix, logger)`: Context manager

## Testing

The threading utilities are fully tested with 100% code coverage. See [tests/unit/test_threading_utils.py](../tests/unit/test_threading_utils.py) for examples.

Run tests:
```bash
pytest tests/unit/test_threading_utils.py -v
```

## See Also

- [Python concurrent.futures documentation](https://docs.python.org/3/library/concurrent.futures.html)
- [Threading best practices](https://realpython.com/intro-to-python-threading/)
