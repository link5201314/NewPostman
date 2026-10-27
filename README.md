# NewPostman
使用 Python 與 PySide6 開發的輕量 API 測試工具，聚焦於參數化與批次鏈式執行。

## 文件

- [架構設計](docs/architecture.md)
- [核心資料模型與引擎原型](docs/core-prototype.md)
- [領域詞彙](CONTEXT.md)

## uv 開發環境

本專案使用 uv 管理 Python 版本、虛擬環境與依賴套件：

```powershell
uv sync
uv run newpostman
```

新增正式依賴：`uv add <套件名稱>`；新增開發依賴：`uv add --dev <套件名稱>`。提交 `pyproject.toml` 與 `uv.lock` 以確保環境可重現。

執行測試：

```powershell
uv run pytest
```

## 目前功能

目前已完成單次 HTTP Request 編輯與送出、Response 狀態碼／耗時／Headers／Body 檢視，以及 Environment 管理與變數替換。支援建立、重新命名、編輯與刪除 Environment；作用環境儲存在本機 Project JSON，並可用 `{{variable_name}}` 替換 Request 的 URL、Headers、Params 與 Body。預設 Project 索引位於使用者家目錄的 `.newpostman/project.json`，Environment 設定存於同目錄下的 `environments/`。Collection 工作區、Runner、Extractor 與 Dataset 仍在規劃中。
