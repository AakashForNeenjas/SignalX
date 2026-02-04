"""Thread pool utilities for managed background task execution."""

import threading
import logging
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Optional, Any, Dict
from contextlib import contextmanager


class ManagedThreadPool:
    """Managed thread pool for background task execution.

    Provides a thread pool with automatic cleanup, error handling,
    and integration with logging. Suitable for long-running applications
    that need reliable background task execution.
    """

    def __init__(
        self,
        max_workers: int = 4,
        thread_name_prefix: str = "Worker",
        logger: Optional[logging.Logger] = None
    ) -> None:
        """Initialize ManagedThreadPool.

        Args:
            max_workers: Maximum number of worker threads
            thread_name_prefix: Prefix for worker thread names
            logger: Optional logger for task execution logging
        """
        self.max_workers = max_workers
        self.thread_name_prefix = thread_name_prefix
        self.logger = logger
        self._executor: Optional[ThreadPoolExecutor] = None
        self._lock = threading.RLock()
        self._active_futures: Dict[str, Future] = {}
        self._shutdown = False

    def _ensure_executor(self) -> ThreadPoolExecutor:
        """Ensure thread pool executor is initialized.

        Returns:
            ThreadPoolExecutor instance
        """
        with self._lock:
            if self._executor is None or self._shutdown:
                self._executor = ThreadPoolExecutor(
                    max_workers=self.max_workers,
                    thread_name_prefix=self.thread_name_prefix
                )
                self._shutdown = False
            return self._executor

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        task_name: Optional[str] = None,
        **kwargs: Any
    ) -> Future:
        """Submit a task to the thread pool.

        Args:
            fn: Callable to execute in thread pool
            *args: Positional arguments for callable
            task_name: Optional name for tracking this task
            **kwargs: Keyword arguments for callable

        Returns:
            Future object for the submitted task
        """
        executor = self._ensure_executor()

        def wrapped_fn() -> Any:
            """Wrapper that adds logging and error handling."""
            if self.logger:
                self.logger.debug(
                    f"Task started: {task_name or fn.__name__}"
                )
            try:
                result = fn(*args, **kwargs)
                if self.logger:
                    self.logger.debug(
                        f"Task completed: {task_name or fn.__name__}"
                    )
                return result
            except Exception as e:
                if self.logger:
                    self.logger.error(
                        f"Task failed: {task_name or fn.__name__}: {e}",
                        exc_info=True
                    )
                raise

        future = executor.submit(wrapped_fn)

        # Track future if task name provided
        if task_name:
            with self._lock:
                self._active_futures[task_name] = future
                # Add callback to remove from tracking when done
                future.add_done_callback(
                    lambda f: self._remove_future(task_name)
                )

        return future

    def _remove_future(self, task_name: str) -> None:
        """Remove completed future from tracking.

        Args:
            task_name: Name of the task to remove
        """
        with self._lock:
            self._active_futures.pop(task_name, None)

    def cancel_task(self, task_name: str) -> bool:
        """Cancel a tracked task by name.

        Args:
            task_name: Name of the task to cancel

        Returns:
            True if task was cancelled, False otherwise
        """
        with self._lock:
            future = self._active_futures.get(task_name)
            if future:
                return future.cancel()
            return False

    def is_task_running(self, task_name: str) -> bool:
        """Check if a tracked task is still running.

        Args:
            task_name: Name of the task to check

        Returns:
            True if task is running, False otherwise
        """
        with self._lock:
            future = self._active_futures.get(task_name)
            if future:
                return future.running()
            return False

    def wait_for_task(
        self,
        task_name: str,
        timeout: Optional[float] = None
    ) -> Optional[Any]:
        """Wait for a tracked task to complete.

        Args:
            task_name: Name of the task to wait for
            timeout: Optional timeout in seconds

        Returns:
            Task result if completed, None if not found or timeout
        """
        with self._lock:
            future = self._active_futures.get(task_name)

        if future:
            try:
                return future.result(timeout=timeout)
            except Exception:
                return None
        return None

    def shutdown(self, wait: bool = True, timeout: Optional[float] = None) -> None:
        """Shutdown the thread pool.

        Args:
            wait: If True, wait for all tasks to complete
            timeout: Optional timeout in seconds for waiting
        """
        with self._lock:
            if self._executor and not self._shutdown:
                self._executor.shutdown(wait=wait, cancel_futures=not wait)
                self._shutdown = True
                self._active_futures.clear()

    def __enter__(self) -> "ManagedThreadPool":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit with cleanup."""
        self.shutdown(wait=True)


# Global thread pool instance for shared use
_global_thread_pool: Optional[ManagedThreadPool] = None
_global_pool_lock = threading.Lock()


def get_global_thread_pool(
    max_workers: int = 4,
    logger: Optional[logging.Logger] = None
) -> ManagedThreadPool:
    """Get or create the global thread pool instance.

    Args:
        max_workers: Maximum number of worker threads (only used on first call)
        logger: Optional logger (only used on first call)

    Returns:
        Global ManagedThreadPool instance
    """
    global _global_thread_pool

    with _global_pool_lock:
        if _global_thread_pool is None:
            _global_thread_pool = ManagedThreadPool(
                max_workers=max_workers,
                thread_name_prefix="GlobalWorker",
                logger=logger
            )
        return _global_thread_pool


def shutdown_global_thread_pool(wait: bool = True) -> None:
    """Shutdown the global thread pool.

    Args:
        wait: If True, wait for all tasks to complete
    """
    global _global_thread_pool

    with _global_pool_lock:
        if _global_thread_pool is not None:
            _global_thread_pool.shutdown(wait=wait)
            _global_thread_pool = None


@contextmanager
def thread_pool_context(
    max_workers: int = 4,
    thread_name_prefix: str = "Worker",
    logger: Optional[logging.Logger] = None
):
    """Context manager for a temporary thread pool.

    Args:
        max_workers: Maximum number of worker threads
        thread_name_prefix: Prefix for worker thread names
        logger: Optional logger for task execution

    Yields:
        ManagedThreadPool instance

    Example:
        with thread_pool_context(max_workers=2) as pool:
            future = pool.submit(my_function, arg1, arg2)
            result = future.result()
    """
    pool = ManagedThreadPool(
        max_workers=max_workers,
        thread_name_prefix=thread_name_prefix,
        logger=logger
    )
    try:
        yield pool
    finally:
        pool.shutdown(wait=True)
