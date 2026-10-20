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
uv run main.py
```

新增正式依賴：`uv add <套件名稱>`；新增開發依賴：`uv add --dev <套件名稱>`。提交 `pyproject.toml` 與 `uv.lock` 以確保環境可重現。
