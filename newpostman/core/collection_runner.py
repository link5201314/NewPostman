from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)


class RunItemResult(BaseModel):
    """Collection 中單一 Request 的執行結果。"""

    index: int
    total: int
    request_id: UUID
    request_name: str
    result: ApiResult
    iteration_index: int = 1
    iteration_total: int = 1


class RunSummary(BaseModel):
    """一次 Collection Runner 執行的摘要。"""

    total: int
    succeeded: int
    failed: int
    cancelled: bool
    iterations: int
    completed_iterations: int
    error: str | None = None


class _RunnerThread(QThread):
    """在 Qt 背景執行緒執行指定 Collection。"""

    def __init__(
        self,
        runner: CollectionRunner,
        collection: CollectionModel,
        environment: EnvironmentModel | None,
        cancellation_event: Event,
        run_context: RunContext | None,
        dataset_rows: list[dict[str, str]] | None,
    ) -> None:
        super().__init__()
        self._runner = runner
        self._collection = collection
        self._environment = environment
        self._run_context = run_context
        self._dataset_rows = dataset_rows
        self._cancellation_event = cancellation_event

    def run(self) -> None:
        """於背景執行緒執行 Runner 工作。"""
        self._runner._execute(
            self._collection,
            self._cancellation_event,
            environment=self._environment,
            run_context=self._run_context,
            dataset_rows=self._dataset_rows,
        )


class CollectionRunner(QObject):
    """依序執行 Collection Request，並以 Qt Signals 回報執行狀態。"""

    progress = Signal(int, int)
    log = Signal(str)
    request_completed = Signal(object)
    iteration_progress = Signal(int, int, int, int)
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
        dataset_rows: list[dict[str, str]] | None = None,
    ) -> bool:
        """在 QThread 背景啟動 Collection；執行中時不啟動第二次。

        Args:
            collection: 依清單順序執行的 Collection。
            environment: 本次執行使用的作用 Environment。
            run_context: 可提供既有執行變數的上下文；未提供時由 Environment 建立。
            dataset_rows: Dataset Data row；None 表示沒有 Dataset，空清單表示零次迭代。

        Returns:
            成功啟動時回傳 True；已有 Runner 工作時回傳 False。
        """
        cancellation_event = self._begin_run()
        if cancellation_event is None:
            return False

        thread = _RunnerThread(
            self,
            collection,
            environment,
            cancellation_event,
            run_context,
            dataset_rows,
        )
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
        dataset_rows: list[dict[str, str]] | None = None,
    ) -> RunSummary:
        """同步執行 Collection，供整合測試及非 UI 呼叫端使用。

        Args:
            collection: 依清單順序執行的 Collection。
            environment: 本次執行使用的作用 Environment。
            cancellation_event: 可選取消事件；設定後不再啟動下一個 Request。
            run_context: 可選的完整執行上下文，包含執行期及資料列變數。
            dataset_rows: Dataset Data row；None 表示沒有 Dataset，空清單表示零次迭代。

        Returns:
            含成功、失敗及取消狀態的執行摘要。

        Raises:
            RuntimeError: Runner 已有背景工作執行中。
        """
        event = self._begin_run(cancellation_event or Event())
        if event is None:
            raise RuntimeError("Runner 已在執行中。")
        return self._execute(
            collection,
            event,
            environment=environment,
            run_context=run_context,
            dataset_rows=dataset_rows,
        )

    def _begin_run(
        self,
        cancellation_event: Event | None = None,
    ) -> Event | None:
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
        cancellation_event: Event,
        *,
        environment: EnvironmentModel | None = None,
        run_context: RunContext | None = None,
        dataset_rows: list[dict[str, str]] | None = None,
    ) -> RunSummary:
        """逐列建立 RunContext 並依 Collection 順序執行所有 Request。

        Args:
            collection: 本次要執行的 Collection。
            cancellation_event: 設定後停止啟動後續 Request。
            environment: 本次執行使用的作用 Environment。
            run_context: 無 Dataset 時可重用的完整執行上下文。
            dataset_rows: 每筆資料列各自建立一輪執行上下文。

        Returns:
            包含 Request 結果與完成 Iteration 數的摘要。
        """
        succeeded = 0
        failed = 0
        rows: list[dict[str, str] | None] = (
            [*dataset_rows] if dataset_rows is not None else [None]
        )
        iterations = len(rows)
        request_total = len(collection.requests)
        total = iterations * request_total
        completed = 0
        completed_iterations = 0
        fatal_error: str | None = None
        selected_environment = (
            run_context.environment if run_context is not None else environment
        )
        self._emit_log(
            f"開始執行 Collection：{collection.name}（{iterations} 個 Iteration，"
            f"共 {total} 個 Request）"
        )
        try:
            with ApiEngine(client=self._client) as engine:
                for iteration_index, data_row in enumerate(rows, start=1):
                    if cancellation_event.is_set():
                        break
                    iteration_context = (
                        RunContext(
                            environment=selected_environment,
                            data_row=data_row or {},
                        )
                        if dataset_rows is not None
                        else run_context
                        or RunContext(environment=selected_environment)
                    )
                    self._emit_log(
                        f"開始 Iteration {iteration_index}/{iterations}"
                    )
                    iteration_completed = 0
                    for request_index, request in enumerate(
                        collection.requests,
                        start=1,
                    ):
                        if cancellation_event.is_set():
                            break
                        self._emit_log(
                            f"Iteration {iteration_index}/{iterations}，"
                            f"Request {request_index}/{request_total}："
                            f"{request.name}"
                        )
                        result = engine.execute(
                            request,
                            run_context=iteration_context,
                        )
                        item_result = RunItemResult(
                            index=request_index,
                            total=request_total,
                            request_id=request.id,
                            request_name=request.name,
                            result=result,
                            iteration_index=iteration_index,
                            iteration_total=iterations,
                        )
                        completed += 1
                        iteration_completed += 1
                        if (
                            result.error is None
                            and result.response is not None
                        ):
                            succeeded += 1
                            self._emit_log(
                                f"Iteration {iteration_index}/{iterations}，"
                                f"Request {request_index}/{request_total}："
                                f"HTTP {result.response.status_code}"
                            )
                        else:
                            failed += 1
                            self._emit_log(
                                f"Iteration {iteration_index}/{iterations}，"
                                f"Request {request_index}/{request_total} "
                                f"{request.name}："
                                f"失敗－{result.error}",
                                logging.ERROR,
                            )
                        for warning in result.warnings:
                            self._emit_log(
                                f"Request 警告－{warning}",
                                logging.WARNING,
                            )
                        self.request_completed.emit(item_result)
                        self.progress.emit(completed, total)
                        self.iteration_progress.emit(
                            iteration_index,
                            iterations,
                            request_index,
                            request_total,
                        )
                    if iteration_completed == request_total:
                        completed_iterations += 1
                        if request_total == 0:
                            self.iteration_progress.emit(
                                iteration_index,
                                iterations,
                                0,
                                0,
                            )
                    if (
                        cancellation_event.is_set()
                        and iteration_completed < request_total
                    ):
                        break
        except Exception as exc:
            fatal_error = str(exc)
            logger.exception("Collection Runner 發生未預期例外")
            self._emit_log(
                f"Runner 發生未預期錯誤：{exc}",
                logging.ERROR,
            )
        finally:
            summary = RunSummary(
                total=total,
                succeeded=succeeded,
                failed=failed,
                cancelled=cancellation_event.is_set(),
                iterations=iterations,
                completed_iterations=completed_iterations,
                error=fatal_error,
            )
            self._emit_log(
                f"執行完成：成功 {succeeded}，失敗 {failed}，"
                f"完成 {completed_iterations}/{iterations} 個 Iteration，"
                f"共 {total} 個 Request"
                f"{'（已取消）' if summary.cancelled else ''}"
            )
            with self._state_lock:
                self._running = False
                self._cancellation_event = None
            self.run_finished.emit(summary)
        return summary

    def _emit_log(self, message: str, level: int = logging.INFO) -> None:
        """同時寫入應用程式日誌與 Runner 工作分頁。"""
        logger.log(level, message)
        self.log.emit(message)

    def _clear_thread(self, finished_thread: _RunnerThread) -> None:
        """清除已結束的 QThread 參照並排程 Qt 物件釋放。"""
        if self._thread is finished_thread:
            self._thread = None
        finished_thread.deleteLater()
