from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from newpostman.models.collection import CollectionModel
from newpostman.models.environment import EnvironmentModel

logger = logging.getLogger(__name__)


class ProjectIndex(BaseModel):
    """Project JSON 索引，保存資源相對路徑與 Environment 作用中識別碼。"""

    environments: dict[str, str] = Field(default_factory=dict)
    collections: dict[str, str] = Field(default_factory=dict)
    active_environment_id: UUID | None = None


class ProjectStoreError(ValueError):
    """Project 或 Environment JSON 讀寫失敗。"""


class ProjectStore:
    """以 project.json 索引及獨立 JSON 檔案管理 Environment。"""

    def __init__(self, project_path: Path) -> None:
        """開啟或初始化 Project 儲存空間。

        Args:
            project_path: Project 索引 JSON 的本機路徑。
        """
        self.project_path = project_path.resolve()
        self.project_root = self.project_path.parent
        self.environment_directory = self.project_root / "environments"
        self.collection_directory = self.project_root / "collections"
        self.environment_directory.mkdir(parents=True, exist_ok=True)
        self.collection_directory.mkdir(parents=True, exist_ok=True)
        self._index = self._load_index()

    def list_environments(self) -> list[EnvironmentModel]:
        """依 Project 索引順序載入所有 Environment。

        Returns:
            Project 中登錄的 Environment 清單。
        """
        return [
            self.get_environment(UUID(environment_id))
            for environment_id in self._index.environments
        ]

    def get_environment(self, environment_id: UUID) -> EnvironmentModel:
        """依識別碼載入並驗證 Environment。

        Args:
            environment_id: Environment 的唯一識別碼。

        Returns:
            讀取並驗證後的 Environment。

        Raises:
            ProjectStoreError: 找不到 Environment 或其 JSON 無效。
        """
        relative_path = self._index.environments.get(str(environment_id))
        if relative_path is None:
            raise ProjectStoreError(f"找不到 Environment：{environment_id}")

        environment_path = self._resolve_environment_path(relative_path)
        try:
            with environment_path.open("r", encoding="utf-8") as file:
                environment = EnvironmentModel.model_validate_json(file.read())
            if environment.id != environment_id:
                raise ProjectStoreError(
                    f"Environment 檔案識別碼與 Project 索引不符：{environment_path.name}"
                )
            return environment
        except ProjectStoreError:
            raise
        except (OSError, ValueError) as exc:
            raise ProjectStoreError(
                f"無法載入 Environment {environment_path.name}：{exc}"
            ) from exc

    def add_environment(
        self,
        environment: EnvironmentModel,
    ) -> EnvironmentModel:
        """新增 Environment 並以相對路徑登錄於 Project。

        Args:
            environment: 要新增的 Environment。

        Returns:
            已儲存的 Environment。
        """
        environment_id = str(environment.id)
        if environment_id in self._index.environments:
            raise ProjectStoreError(f"Environment 識別碼已存在：{environment.id}")
        environment_path = self.environment_directory / f"{environment.id}.json"
        relative_path = environment_path.relative_to(self.project_root).as_posix()
        previous_active_id = self._index.active_environment_id
        self._index.environments[environment_id] = relative_path
        if self._index.active_environment_id is None:
            self._index.active_environment_id = environment.id
        try:
            self._save_environment(environment)
            self._save_index()
        except ProjectStoreError:
            self._index.environments.pop(environment_id, None)
            self._index.active_environment_id = previous_active_id
            try:
                environment_path.unlink(missing_ok=True)
            except OSError:
                logger.warning(
                    "無法清理新增失敗的 Environment 檔案：%s",
                    environment_path,
                    exc_info=True,
                )
            raise
        return environment

    def update_environment(
        self,
        environment: EnvironmentModel,
    ) -> EnvironmentModel:
        """更新已存在 Environment 的名稱及變數。

        Args:
            environment: 含有既有識別碼及更新值的 Environment。

        Returns:
            已儲存的 Environment。

        Raises:
            ProjectStoreError: 該識別碼尚未登錄於 Project。
        """
        if str(environment.id) not in self._index.environments:
            raise ProjectStoreError(f"找不到 Environment：{environment.id}")
        self._save_environment(environment)
        return environment

    def remove_environment(self, environment_id: UUID) -> None:
        """移除 Environment；若目前作用中則清除選擇。

        Args:
            environment_id: 要移除的 Environment 識別碼。
        """
        relative_path = self._index.environments.get(str(environment_id))
        if relative_path is None:
            return
        environment_path = self._resolve_environment_path(relative_path)
        previous_active_id = self._index.active_environment_id
        self._index.environments.pop(str(environment_id))
        if self._index.active_environment_id == environment_id:
            self._index.active_environment_id = None
        try:
            self._save_index()
        except ProjectStoreError:
            self._index.environments[str(environment_id)] = relative_path
            self._index.active_environment_id = previous_active_id
            raise
        try:
            environment_path.unlink(missing_ok=True)
        except OSError as exc:
            raise ProjectStoreError(
                f"無法移除 Environment 檔案 {environment_path.name}：{exc}"
            ) from exc

    def set_active_environment(self, environment_id: UUID | None) -> None:
        """設定目前作用 Environment；None 表示不選用環境。

        Args:
            environment_id: 已登錄的識別碼，或 None。

        Raises:
            ProjectStoreError: 識別碼未登錄於 Project。
        """
        if (
            environment_id is not None
            and str(environment_id) not in self._index.environments
        ):
            raise ProjectStoreError(f"找不到 Environment：{environment_id}")
        previous_active_id = self._index.active_environment_id
        self._index.active_environment_id = environment_id
        try:
            self._save_index()
        except ProjectStoreError:
            self._index.active_environment_id = previous_active_id
            raise

    def active_environment(self) -> EnvironmentModel | None:
        """取得目前作用 Environment。

        Returns:
            作用 Environment；未選取時回傳 None。
        """
        environment_id = self._index.active_environment_id
        if environment_id is None:
            return None
        return self.get_environment(environment_id)

    def list_collections(self) -> list[CollectionModel]:
        """依 Project 索引順序載入所有 Collection。

        Returns:
            Project 中登錄的 Collection 清單。
        """
        return [
            self.get_collection(UUID(collection_id))
            for collection_id in self._index.collections
        ]

    def get_collection(self, collection_id: UUID) -> CollectionModel:
        """依識別碼載入並驗證 Collection。

        Args:
            collection_id: Collection 的唯一識別碼。

        Returns:
            讀取並驗證後的 Collection。

        Raises:
            ProjectStoreError: 找不到 Collection 或 JSON 無效。
        """
        relative_path = self._index.collections.get(str(collection_id))
        if relative_path is None:
            raise ProjectStoreError(f"找不到 Collection：{collection_id}")
        collection_path = self._resolve_collection_path(relative_path)
        try:
            with collection_path.open("r", encoding="utf-8") as file:
                collection = CollectionModel.model_validate_json(file.read())
            if collection.id != collection_id:
                raise ProjectStoreError(
                    f"Collection 檔案識別碼與 Project 索引不符：{collection_path.name}"
                )
            return collection
        except ProjectStoreError:
            raise
        except (OSError, ValueError) as exc:
            raise ProjectStoreError(
                f"無法載入 Collection {collection_path.name}：{exc}"
            ) from exc

    def add_collection(self, collection: CollectionModel) -> CollectionModel:
        """新增 Collection，並於 Project 索引記錄相對路徑。

        Args:
            collection: 要新增的 Collection。

        Returns:
            已儲存的 Collection。
        """
        collection_id = str(collection.id)
        if collection_id in self._index.collections:
            raise ProjectStoreError(f"Collection 識別碼已存在：{collection.id}")
        collection_path = self.collection_directory / f"{collection.id}.json"
        relative_path = collection_path.relative_to(self.project_root).as_posix()
        self._index.collections[collection_id] = relative_path
        try:
            self._save_collection(collection)
            self._save_index()
        except ProjectStoreError:
            self._index.collections.pop(collection_id, None)
            try:
                collection_path.unlink(missing_ok=True)
            except OSError:
                logger.warning(
                    "無法清理新增失敗的 Collection 檔案：%s",
                    collection_path,
                    exc_info=True,
                )
            raise
        return collection

    def update_collection(self, collection: CollectionModel) -> CollectionModel:
        """更新已存在 Collection 的名稱、順序或 Request。

        Args:
            collection: 含有已登錄識別碼及更新值的 Collection。

        Returns:
            已儲存的 Collection。

        Raises:
            ProjectStoreError: 該識別碼尚未登錄於 Project。
        """
        if str(collection.id) not in self._index.collections:
            raise ProjectStoreError(f"找不到 Collection：{collection.id}")
        self._save_collection(collection)
        return collection

    def remove_collection(self, collection_id: UUID) -> None:
        """移除 Project 中的 Collection 及其 JSON 檔案。

        Args:
            collection_id: 要移除的 Collection 識別碼。
        """
        relative_path = self._index.collections.get(str(collection_id))
        if relative_path is None:
            return
        collection_path = self._resolve_collection_path(relative_path)
        self._index.collections.pop(str(collection_id))
        try:
            self._save_index()
        except ProjectStoreError:
            self._index.collections[str(collection_id)] = relative_path
            raise
        try:
            collection_path.unlink(missing_ok=True)
        except OSError as exc:
            raise ProjectStoreError(
                f"無法移除 Collection 檔案 {collection_path.name}：{exc}"
            ) from exc

    def _load_index(self) -> ProjectIndex:
        """讀取 Project 索引；不存在時建立空白索引。

        Returns:
            已驗證的 ProjectIndex。

        Raises:
            ProjectStoreError: 索引 JSON 無法讀取或驗證。
        """
        if not self.project_path.exists():
            self._index = ProjectIndex()
            self._save_index()
            return self._index
        try:
            with self.project_path.open("r", encoding="utf-8") as file:
                index = ProjectIndex.model_validate_json(file.read())
            active_id = index.active_environment_id
            if active_id is not None and str(active_id) not in index.environments:
                raise ProjectStoreError(
                    "Project 索引的作用中 Environment 未登錄於環境清單。"
                )
            return index
        except ProjectStoreError:
            raise
        except (OSError, ValueError) as exc:
            raise ProjectStoreError(
                f"無法載入 Project 索引 {self.project_path.name}：{exc}"
            ) from exc

    def _save_index(self) -> None:
        """以原子檔案替換方式保存 Project 索引。"""
        self._write_json(self.project_path, self._index.model_dump(mode="json"))

    def _save_environment(self, environment: EnvironmentModel) -> None:
        """將 Environment 寫入索引所指向的 JSON 檔案。

        Args:
            environment: 要保存的 Environment。
        """
        relative_path = self._index.environments[str(environment.id)]
        self._write_json(
            self.project_root / relative_path,
            environment.model_dump(mode="json"),
        )

    def _resolve_environment_path(self, relative_path: str) -> Path:
        """解析並限制 Environment 檔案位於 Project 目錄內。

        Args:
            relative_path: Project 索引中的 Environment 相對路徑。

        Returns:
            經正規化並確認範圍安全的 Environment 檔案路徑。

        Raises:
            ProjectStoreError: 路徑試圖離開 Project 根目錄。
        """
        environment_path = (self.project_root / relative_path).resolve()
        if not environment_path.is_relative_to(self.environment_directory.resolve()):
            raise ProjectStoreError("Environment 路徑必須位於 environments 目錄內。")
        return environment_path

    def _resolve_collection_path(self, relative_path: str) -> Path:
        """解析並限制 Collection 檔案位於 Project collections 目錄內。

        Args:
            relative_path: Project 索引中的 Collection 相對路徑。

        Returns:
            經正規化並確認範圍安全的 Collection 檔案路徑。

        Raises:
            ProjectStoreError: 路徑試圖離開 collections 目錄。
        """
        collection_path = (self.project_root / relative_path).resolve()
        if not collection_path.is_relative_to(self.collection_directory.resolve()):
            raise ProjectStoreError("Collection 路徑必須位於 collections 目錄內。")
        return collection_path

    def _save_collection(self, collection: CollectionModel) -> None:
        """將 Collection 寫入索引所指向的 JSON 檔案。

        Args:
            collection: 要保存的 Collection。
        """
        relative_path = self._index.collections[str(collection.id)]
        self._write_json(
            self.project_root / relative_path,
            collection.model_dump(mode="json"),
        )

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(f"{path.suffix}.tmp")
        try:
            with temporary_path.open("w", encoding="utf-8", newline="\n") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.write("\n")
            temporary_path.replace(path)
        except OSError as exc:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                logger.warning(
                    "無法清理暫存 JSON 檔案：%s",
                    temporary_path,
                    exc_info=True,
                )
            raise ProjectStoreError(f"無法寫入 {path.name}：{exc}") from exc
