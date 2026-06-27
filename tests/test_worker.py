"""Tests for the worker/thread lifecycle."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal

from hmi.core.worker import PeriodicWorker, Worker, WorkerThread


class _Adder(Worker):
    done = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__(name="adder")
        self.result = 0

    def work(self) -> None:
        self.result = 21 + 21
        self.done.emit(self.result)


def test_worker_runs_and_finishes(qtbot):
    worker = _Adder()
    thread = WorkerThread(worker, name="adder")

    with qtbot.waitSignal(worker.finished, timeout=2000):
        thread.start()

    assert worker.result == 42
    thread.stop()


class _FailingWorker(Worker):
    def work(self) -> None:
        raise ValueError("boom in thread")


def test_worker_failure_emitted_not_crashing(qtbot):
    worker = _FailingWorker()
    thread = WorkerThread(worker, name="failer")

    with qtbot.waitSignal(worker.failed, timeout=2000) as blocker:
        thread.start()

    fault = blocker.args[0]
    assert "boom in thread" in fault.message
    thread.stop()


class _Counter(PeriodicWorker):
    ticked = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__(interval_ms=10, name="counter")
        self.count = 0

    def step(self) -> None:
        self.count += 1
        self.ticked.emit(self.count)


def test_periodic_worker_ticks_and_stops(qtbot):
    worker = _Counter()
    thread = WorkerThread(worker, name="counter")
    thread.start()

    qtbot.waitUntil(lambda: worker.count >= 3, timeout=2000)
    thread.stop()  # exercises the queued stop() + thread join

    settled = worker.count
    qtbot.wait(50)
    assert worker.count == settled  # no ticks after stop
