"""Unit tests for threading utilities."""

import time
import threading
import pytest
from unittest.mock import Mock
from concurrent.futures import TimeoutError as FuturesTimeoutError

from core.threading_utils import (
    ManagedThreadPool,
    get_global_thread_pool,
    shutdown_global_thread_pool,
    thread_pool_context
)


@pytest.mark.unit
class TestManagedThreadPool:
    """Test suite for ManagedThreadPool class."""

    def test_init(self):
        """Test ManagedThreadPool initialization."""
        pool = ManagedThreadPool(max_workers=2, thread_name_prefix="Test")

        assert pool.max_workers == 2
        assert pool.thread_name_prefix == "Test"
        assert pool.logger is None
        assert pool._executor is None

    def test_init_with_logger(self):
        """Test initialization with logger."""
        mock_logger = Mock()
        pool = ManagedThreadPool(logger=mock_logger)

        assert pool.logger == mock_logger

    def test_submit_simple_task(self):
        """Test submitting a simple task."""
        pool = ManagedThreadPool(max_workers=2)

        def simple_task(x):
            return x * 2

        future = pool.submit(simple_task, 5)
        result = future.result(timeout=1.0)

        assert result == 10

        pool.shutdown()

    def test_submit_with_kwargs(self):
        """Test submitting task with keyword arguments."""
        pool = ManagedThreadPool()

        def task_with_kwargs(a, b=10):
            return a + b

        future = pool.submit(task_with_kwargs, 5, b=20)
        result = future.result(timeout=1.0)

        assert result == 25

        pool.shutdown()

    def test_submit_with_task_name(self):
        """Test submitting task with name for tracking."""
        pool = ManagedThreadPool()

        def slow_task():
            time.sleep(0.1)
            return "done"

        future = pool.submit(slow_task, task_name="slow_task")

        assert pool.is_task_running("slow_task")
        result = future.result(timeout=1.0)
        assert result == "done"

        # After completion, should be removed from tracking
        time.sleep(0.1)
        assert not pool.is_task_running("slow_task")

        pool.shutdown()

    def test_submit_multiple_tasks(self):
        """Test submitting multiple tasks concurrently."""
        pool = ManagedThreadPool(max_workers=3)

        results = []

        def task(n):
            time.sleep(0.05)
            return n * 2

        futures = [pool.submit(task, i) for i in range(5)]

        for future in futures:
            results.append(future.result(timeout=1.0))

        assert results == [0, 2, 4, 6, 8]

        pool.shutdown()

    def test_task_with_exception(self):
        """Test task that raises exception."""
        mock_logger = Mock()
        pool = ManagedThreadPool(logger=mock_logger)

        def failing_task():
            raise ValueError("Test error")

        future = pool.submit(failing_task, task_name="failing")

        with pytest.raises(ValueError, match="Test error"):
            future.result(timeout=1.0)

        # Logger should have recorded the error
        assert mock_logger.error.called

        pool.shutdown()

    def test_cancel_task(self):
        """Test cancelling a running task."""
        pool = ManagedThreadPool()

        def long_task():
            time.sleep(2.0)
            return "done"

        future = pool.submit(long_task, task_name="long_task")

        # Try to cancel (may or may not succeed depending on timing)
        cancelled = pool.cancel_task("long_task")

        # If cancelled successfully, should not be running
        if cancelled:
            assert not pool.is_task_running("long_task")

        pool.shutdown(wait=False)

    def test_cancel_nonexistent_task(self):
        """Test cancelling a task that doesn't exist."""
        pool = ManagedThreadPool()

        cancelled = pool.cancel_task("nonexistent")
        assert cancelled is False

        pool.shutdown()

    def test_is_task_running(self):
        """Test checking if task is running."""
        pool = ManagedThreadPool()

        def quick_task():
            return "done"

        # Task not submitted yet
        assert not pool.is_task_running("quick")

        future = pool.submit(quick_task, task_name="quick")
        future.result(timeout=1.0)

        # After completion, should not be running
        time.sleep(0.1)
        assert not pool.is_task_running("quick")

        pool.shutdown()

    def test_wait_for_task(self):
        """Test waiting for task completion."""
        pool = ManagedThreadPool()

        def slow_task():
            time.sleep(0.2)
            return "completed"

        pool.submit(slow_task, task_name="slow")

        result = pool.wait_for_task("slow", timeout=1.0)
        assert result == "completed"

        pool.shutdown()

    def test_wait_for_task_timeout(self):
        """Test waiting for task with timeout."""
        pool = ManagedThreadPool()

        def very_slow_task():
            time.sleep(10.0)
            return "done"

        pool.submit(very_slow_task, task_name="very_slow")

        result = pool.wait_for_task("very_slow", timeout=0.1)
        assert result is None

        pool.shutdown(wait=False)

    def test_wait_for_nonexistent_task(self):
        """Test waiting for task that doesn't exist."""
        pool = ManagedThreadPool()

        result = pool.wait_for_task("nonexistent", timeout=0.1)
        assert result is None

        pool.shutdown()

    def test_shutdown(self):
        """Test shutting down thread pool."""
        pool = ManagedThreadPool()

        def task():
            time.sleep(0.1)
            return "done"

        pool.submit(task)
        pool.shutdown(wait=True)

        assert pool._shutdown is True

    def test_shutdown_without_wait(self):
        """Test shutting down without waiting."""
        pool = ManagedThreadPool()

        def long_task():
            time.sleep(5.0)
            return "done"

        pool.submit(long_task)
        pool.shutdown(wait=False)

        assert pool._shutdown is True

    def test_context_manager(self):
        """Test using thread pool as context manager."""
        results = []

        with ManagedThreadPool(max_workers=2) as pool:
            def task(n):
                return n * 2

            futures = [pool.submit(task, i) for i in range(3)]
            for future in futures:
                results.append(future.result())

        assert results == [0, 2, 4]

    def test_logger_debug_messages(self):
        """Test that logger receives debug messages."""
        mock_logger = Mock()
        pool = ManagedThreadPool(logger=mock_logger)

        def task():
            return "done"

        future = pool.submit(task, task_name="test_task")
        future.result(timeout=1.0)

        # Should have called debug for start and completion
        assert mock_logger.debug.call_count >= 2

        pool.shutdown()

    def test_reinitialization_after_shutdown(self):
        """Test that executor can be reinitialized after shutdown."""
        pool = ManagedThreadPool()

        # First use
        future1 = pool.submit(lambda: "first")
        assert future1.result(timeout=1.0) == "first"

        pool.shutdown()

        # Second use after shutdown
        future2 = pool.submit(lambda: "second")
        assert future2.result(timeout=1.0) == "second"

        pool.shutdown()


@pytest.mark.unit
class TestGlobalThreadPool:
    """Test suite for global thread pool functions."""

    def teardown_method(self):
        """Clean up global thread pool after each test."""
        shutdown_global_thread_pool()

    def test_get_global_thread_pool(self):
        """Test getting global thread pool instance."""
        pool1 = get_global_thread_pool()
        pool2 = get_global_thread_pool()

        # Should return same instance
        assert pool1 is pool2

    def test_get_global_thread_pool_with_params(self):
        """Test getting global pool with parameters."""
        mock_logger = Mock()
        pool = get_global_thread_pool(max_workers=3, logger=mock_logger)

        assert pool.max_workers == 3
        assert pool.logger == mock_logger

    def test_global_pool_submit(self):
        """Test submitting task to global pool."""
        pool = get_global_thread_pool()

        def task(x):
            return x * 3

        future = pool.submit(task, 7)
        result = future.result(timeout=1.0)

        assert result == 21

    def test_shutdown_global_thread_pool(self):
        """Test shutting down global thread pool."""
        pool = get_global_thread_pool()
        pool.submit(lambda: "test")

        shutdown_global_thread_pool()

        # New call should create new instance
        new_pool = get_global_thread_pool()
        assert new_pool is not pool


@pytest.mark.unit
class TestThreadPoolContext:
    """Test suite for thread_pool_context context manager."""

    def test_context_manager_basic(self):
        """Test basic usage of context manager."""
        results = []

        with thread_pool_context(max_workers=2) as pool:
            def task(n):
                return n * 2

            futures = [pool.submit(task, i) for i in range(3)]
            for future in futures:
                results.append(future.result())

        assert results == [0, 2, 4]

    def test_context_manager_with_params(self):
        """Test context manager with custom parameters."""
        mock_logger = Mock()

        with thread_pool_context(
            max_workers=3,
            thread_name_prefix="CustomWorker",
            logger=mock_logger
        ) as pool:
            assert pool.max_workers == 3
            assert pool.thread_name_prefix == "CustomWorker"
            assert pool.logger == mock_logger

    def test_context_manager_cleanup(self):
        """Test that context manager cleans up properly."""
        pool_ref = None

        with thread_pool_context() as pool:
            pool_ref = pool
            pool.submit(lambda: "test")

        # Pool should be shutdown after context exit
        assert pool_ref._shutdown is True

    def test_context_manager_with_exception(self):
        """Test context manager cleanup when exception occurs."""
        pool_ref = None

        try:
            with thread_pool_context() as pool:
                pool_ref = pool
                pool.submit(lambda: "test")
                raise ValueError("Test error")
        except ValueError:
            pass

        # Pool should still be shutdown
        assert pool_ref._shutdown is True
