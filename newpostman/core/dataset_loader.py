from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, NoReturn


class DatasetLoadError(ValueError):
    """Dataset 檔案無法辨識或內容驗證失敗。"""


class DatasetLoader:
    """讀取 CSV 或 JSON Dataset，轉成字串型別的 Data row。"""

    @classmethod
    def load(cls, path: Path) -> list[dict[str, str]]:
        """依副檔名讀取 CSV 或 JSON Dataset。

        Args:
            path: Dataset 原始檔案路徑；讀取時不會修改來源。

        Returns:
            依檔案順序排列、值皆為字串的 Data row 清單。

        Raises:
            DatasetLoadError: 副檔名不支援、檔案無法讀取或格式／資料無效。
        """
        dataset_path = path.expanduser().resolve()
        suffix = dataset_path.suffix.lower()
        try:
            if suffix == ".csv":
                return cls._load_csv(dataset_path)
            if suffix == ".json":
                return cls._load_json(dataset_path)
        except (OSError, UnicodeError, csv.Error, json.JSONDecodeError) as exc:
            format_name = "CSV" if suffix == ".csv" else "JSON"
            raise DatasetLoadError(
                f"{format_name} Dataset 格式錯誤或無法讀取 "
                f"{dataset_path.name}：{exc}"
            ) from exc
        raise DatasetLoadError(
            f"不支援 Dataset 格式：{dataset_path.suffix or '（無副檔名）'}；請使用 CSV 或 JSON。"
        )

    @staticmethod
    def _load_csv(path: Path) -> list[dict[str, str]]:
        """以第一列欄名讀取 CSV，略過空白資料列。"""
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.reader(file, strict=True)
            try:
                headers = next(reader)
            except StopIteration as exc:
                raise DatasetLoadError("CSV Dataset 為空，缺少欄名列。") from exc

            normalized_headers = [header.strip() for header in headers]
            if not normalized_headers or any(
                not header for header in normalized_headers
            ):
                raise DatasetLoadError("CSV Dataset 欄名不可為空白。")
            if len(set(normalized_headers)) != len(normalized_headers):
                raise DatasetLoadError("CSV Dataset 欄名不可重複。")

            rows: list[dict[str, str]] = []
            for row_number, values in enumerate(reader, start=2):
                if not values:
                    continue
                if len(values) != len(normalized_headers):
                    raise DatasetLoadError(
                        f"CSV Dataset 第 {row_number} 列欄位數不符："
                        f"預期 {len(normalized_headers)} 欄，實際 {len(values)} 欄。"
                    )
                rows.append(dict(zip(normalized_headers, values, strict=True)))
            return rows

    @classmethod
    def _load_json(cls, path: Path) -> list[dict[str, str]]:
        """讀取由 JSON 物件陣列組成的 Dataset。"""
        with path.open("r", encoding="utf-8-sig") as file:
            payload: Any = json.load(
                file,
                parse_constant=DatasetLoader._reject_nonstandard_constant,
            )
        if not isinstance(payload, list):
            raise DatasetLoadError("JSON Dataset 最外層必須是物件陣列。")

        rows: list[dict[str, str]] = []
        for row_number, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise DatasetLoadError(
                    f"JSON Dataset 第 {row_number} 筆資料必須是物件。"
                )
            row: dict[str, str] = {}
            for key, value in item.items():
                if not isinstance(key, str) or not key.strip():
                    raise DatasetLoadError(
                        f"JSON Dataset 第 {row_number} 筆資料含空白或無效欄名。"
                    )
                row[key] = cls._json_value_to_text(value)
            rows.append(row)
        return rows

    @staticmethod
    def _reject_nonstandard_constant(value: str) -> NoReturn:
        """拒絕 Python JSON parser 額外接受的 NaN／Infinity 常數。"""
        raise json.JSONDecodeError(
            f"JSON Dataset 不允許非標準常數 {value}。",
            value,
            0,
        )

    @staticmethod
    def _json_value_to_text(value: Any) -> str:
        """將 JSON 值轉成 VariableEngine 可插值的文字。"""
        if isinstance(value, str):
            return value
        if value is None:
            return ""
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
