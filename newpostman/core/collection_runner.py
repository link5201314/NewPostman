from __future__ import annotations

from threading import Event, Lock
from uuid import UUID

import httpx
from PySide6.QtCore import QThread, QObject, Signal
from pydantic import BaseModel

from newpostman.core.api_engine import ApiEngine, ApiResult
from newpostman.models.collection import CollectionModel
from newpostman.models.environment import EnvironmentModel
from newpostman.models.request import RequestModel
from newpostman.models.run_context import RunContext


class RunItemResult(BaseModel):
    """Collection 中單一 Request 的執行結果。"""

    index: int
    total: int
    request_id: UUID
    request_name: str
    result: ApiResult


class RunSummary(BaseModel):
    """一次 Collection Runner 執行的摘要。"""

    total: int
    succeeded: int
    failed: int
    cancelled: bool


class _RunnerThread(QThread):
    """在 Qt 背景執行緒執行指定 Collection。"""

    def __init__(
        self,
        runner: CollectionRunner,
        collection: CollectionModel,
        run_context: RunContext,
        cancellation_event: Event,
    ) -> None:
        super().__init__()
        self._runner = runner
        self._collection = collection
        self._run_context = run_context
        self._cancellation_event = cancellation_event

    def run(self) -> None:
        """於背景執行緒執行 Runner 工作。"""
        self._runner._execute(
            self._collection,
            self._run_context,
            self._cancellation_event,
        )


class CollectionRunner(QObject):
    """依序執行 Collection Request，並以 Qt Signals 回報執行狀態。"""

    progress = Signal(int, int)
    log = Signal(str)
    request_completed = Signal(object)
    run_finished = Signal(object)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        """建立 Collection Runner。

        Args:
            parent: 可選的 Qt 父物件。
            client: 可選的 HTTPX Client，方便注入 MockTransport。
        """
        super().__init__(parent)
        self._client = client
        self._state_lock = Lock()
        self._running = False
        self._cancellation_event: Event | None = None
        self._thread: _RunnerThread | None = None

    @property
    def is_running(self) -> bool:
        """目前是否有 Runner 工作正在執行。"""
        with self._state_lock:
            return self._running

    def start(
        self,
        collection: CollectionModel,
        environment: EnvironmentModel | None = None,
        *,
        run_context: RunContext | None = None,
    ) -> bool:
        """在 QThread 背景啟動 Collection；執行中時不啟動第二次。

        Args:
            collection: 依清單順序執行的 Collection。
            environment: 本次執行使用的作用 Environment。
            run_context: 可提供既有執行變數的上下文；未提供時由 Environment 建立。

        Returns:
            成功啟動時回傳 True；已有 Runner 工作時回傳 False。
        """
        cancellation_event = self._begin_run()
        if cancellation_event is None:
            return False

        context = run_context or RunContext(environment=environment)
        thread = _RunnerThread(self, collection, context, cancellation_event)
        thread.finished.connect(lambda: self._clear_thread(thread))
        self._thread = thread
        thread.start()
        return True

    def cancel(self) -> None:
        """要求 Runner 在目前 Request 結束後停止啟動後續 Request。"""
        with self._state_lock:
            cancellation_event = self._cancellation_event
        if cancellation_event is not None:
            cancellation_event.set()

    def run(
        self,
        collection: CollectionModel,
        environment: EnvironmentModel | None = None,
        *,
        cancellation_event: Event | None = None,
        run_context: RunContext | None = None,
    ) -> RunSummary:
        """同步執行 Collection，供整合測試及非 UI 呼叫端使用。

        Args:
            collection: 依清單順序執行的 Collection。
            environment: 本次執行使用的作用 Environment。
            cancellation_event: 可選取消事件；設定後不再啟動下一個 Request。
            run_context: 可選的完整執行上下文，包含執行期及資料列變數。

        Returns:
            含成功、失敗及取消狀態的執行摘要。

        Raises:
            RuntimeError: Runner 已有背景工作執行中。
        """
        event = self._begin_run(cancellation_event or Event())
        if event is None:
            raise RuntimeError("Runner 已在執行中。")
        context = run_context or RunContext(environment=environment)
        return self._execute(collection, context, event)

    def _begin_run(self, cancellation_event: Event | None = None) -> Event | None:
        """原子設定執行狀態並建立本次執行的取消事件。"""
        with self._state_lock:
            if self._running:
                return None
            event = cancellation_event or Event()
            self._running = True
            self._cancellation_event = event
            return event

    def _execute(
        self,
        collection: CollectionModel,
        run_context: RunContext,
        cancellation_event: Event,
    ) -> RunSummary:
        succeeded = 0
        failed = 0
        total = len(collection.requests)
        completed = 0
        self.log.emit(f"開始執行 Collection：{collection.name}（{total} 個 Request）")
        try:
            with ApiEngine(client=self._client) as engine:
                for index, request in enumerate(collection.requests, start=1):
                    if cancellation_event.is_set():
                        break
                    self.log.emit(f"執行 {index}/{total}：{request.name}")
                    result = engine.execute(request, run_context=run_context)
                    item_result = RunItemResult(
                        index=index,
                        total=total,
                        request_id=request.id,
                        request_name=request.name,
                        result=result,
                    )
                    completed += 1
                    if result.error is None and result.response is not None:
                        succeeded += 1
                        self.log.emit(
                            f"{index}/{total} {request.name}：HTTP "
                            f"{result.response.status_code}"
                        )
                    else:
                        failed += 1
                        self.log.emit(
                            f"{index}/{total} {request.name}：失敗－{result.error}"
                        )
                    for warning in result.warnings:
                        self.log.emit(f"{index}/{total} {request.name}：警告－{warning}")
                    self.request_completed.emit(item_result)
                    self.progress.emit(completed, total)
        finally:
            summary = RunSummary(
                total=total,
                succeeded=succeeded,
                failed=failed,
                cancelled=cancellation_event.is_set(),
            )
            self.log.emit(
                f"執行完成：成功 {succeeded}，失敗 {failed}，"
                f"共 {total} 個 Request"
                f"{'（已取消）' if summary.cancelled else ''}"
            )
            with self._state_lock:
                self._running = False
                self._cancellation_event = None
            self.run_finished.emit(summary)
        return summary

    def _clear_thread(self, finished_thread: _RunnerThread) -> None:
        """清除已結束的 QThread 參照並排程 Qt 物件釋放。"""
        if self._thread is finished_thread:
            self._thread = None
        finished_thread.deleteLater()
