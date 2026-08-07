"""Shared process/thread pool helpers for CPU-bound beet plugins."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import (
    Executor,
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)
from multiprocessing import get_context
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


def create_executor(
    task_count: int,
    *,
    thread_name_prefix: str = "worker",
) -> tuple[Executor, int, str]:
    """Choose process or thread workers based on the GIL.

    Restricted environments can deny process semaphore inspection. Falling
    back to threads keeps local/test builds usable without changing output.
    """

    available_workers = min(task_count, os.process_cpu_count() or 1)
    if sys._is_gil_enabled():
        # Large results make IPC the bottleneck beyond a small process pool.
        max_workers = min(available_workers, 4)
        try:
            return (
                ProcessPoolExecutor(
                    max_workers=max_workers,
                    mp_context=get_context("spawn"),
                ),
                max_workers,
                "processes",
            )
        except OSError, PermissionError:
            logger.warning(
                "Process workers unavailable; falling back to regular threads"
            )

    max_workers = min(available_workers, 10)
    return (
        ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix,
        ),
        max_workers,
        "threads",
    )


def map_as_completed(
    fn: Callable[..., R],
    items: Sequence[T],
    *,
    item_id: Callable[[T], str],
    args: Callable[[T], tuple[Any, ...]] | None = None,
    thread_name_prefix: str = "worker",
    failure_message: str = "Failed to process item: %s",
) -> Iterator[tuple[T, R]]:
    """Submit work to a pool and yield ``(item, result)`` as futures complete.

    When ``args`` is omitted, each item is submitted as ``fn(item)``. Otherwise
    ``fn(*args(item))`` is used so multi-argument workers stay picklable for
    process pools. Errors are logged with ``item_id(item)`` and re-raised.
    """

    if not items:
        return

    executor, max_workers, executor_kind = create_executor(
        len(items),
        thread_name_prefix=thread_name_prefix,
    )
    logger.info(
        "Processing %d items with %d %s",
        len(items),
        max_workers,
        executor_kind,
    )

    with executor:
        futures: dict[Future[R], T] = {
            executor.submit(fn, *(args(item) if args else (item,))): item
            for item in items
        }
        for future in as_completed(futures):
            item = futures[future]
            try:
                yield item, future.result()
            except Exception:
                logger.exception(failure_message, item_id(item))
                raise
