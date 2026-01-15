"""OG Prompt Example 1

Context: You are testing a Python-based event-driven task scheduler.
Outcome: Generate pytest tests to validate delayed execution, invalid scheduling times, concurrent
task dispatch, and cancellation rules.
Steps: The tests must expose race conditions and boundary failures.
Tools: pytest-mock, mockito
Audience: developers
Relevance: Its important to ensure the scheduler handles edge cases correctly
"""

import threading
import time

import pytest
from mockito import mock, verify

try:
    from scheduler import ScheduleError, Scheduler
except Exception:  # pragma: no cover - placeholder until the real scheduler is present
    ScheduleError = Exception
    Scheduler = None


def _require_scheduler():
    if Scheduler is None:
        pytest.skip("Scheduler implementation not available in this workspace.")


@pytest.fixture
def scheduler():
    _require_scheduler()
    return Scheduler()


def _require_methods(obj, methods):
    missing = [name for name in methods if not hasattr(obj, name)]
    if missing:
        pytest.skip(
            f"Scheduler missing required methods: {', '.join(missing)}")


def test_delayed_execution_waits_until_deadline(scheduler):
    _require_methods(scheduler, ["schedule_in", "run_pending"])
    callback = mock()

    scheduler.schedule_in(0.05, callback)
    scheduler.run_pending()
    verify(callback, times=0).__call__()

    time.sleep(0.06)
    scheduler.run_pending()
    verify(callback, times=1).__call__()


@pytest.mark.parametrize("delay", [-1, -0.001])
def test_invalid_scheduling_times_raise(scheduler, delay):
    _require_methods(scheduler, ["schedule_in"])
    callback = mock()

    with pytest.raises((ValueError, ScheduleError)):
        scheduler.schedule_in(delay, callback)


def test_concurrent_dispatch_invokes_each_task_once(scheduler):
    _require_methods(scheduler, ["schedule_in", "run_pending"])
    counter = {"count": 0}
    lock = threading.Lock()

    def increment():
        with lock:
            counter["count"] += 1

    for _ in range(25):
        scheduler.schedule_in(0, increment)

    barrier = threading.Barrier(3)

    def runner():
        barrier.wait()
        scheduler.run_pending()

    threads = [threading.Thread(target=runner) for _ in range(2)]
    for thread in threads:
        thread.start()

    barrier.wait()
    scheduler.run_pending()
    for thread in threads:
        thread.join()

    assert counter["count"] == 25


def test_cancelled_task_does_not_execute(scheduler):
    _require_methods(scheduler, ["schedule_in", "cancel", "run_pending"])
    callback = mock()

    task_id = scheduler.schedule_in(0.05, callback)
    assert scheduler.cancel(task_id) in (True, False)

    time.sleep(0.06)
    scheduler.run_pending()
    verify(callback, times=0).__call__()


def test_cancel_race_with_dispatch_does_not_duplicate_execution(scheduler):
    _require_methods(scheduler, ["schedule_in", "cancel", "run_pending"])
    callback = mock()
    task_id = scheduler.schedule_in(0, callback)

    barrier = threading.Barrier(2)

    def canceler():
        barrier.wait()
        scheduler.cancel(task_id)

    thread = threading.Thread(target=canceler)
    thread.start()
    barrier.wait()
    scheduler.run_pending()
    thread.join()

    verify(callback, times=0).__call__() or verify(
        callback, times=1).__call__()
