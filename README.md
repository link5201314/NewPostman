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

目前已完成單次 HTTP Request 編輯與送出、Response 狀態碼／耗時／Headers／Body 檢視、Environment 管理與變數替換、Collection 工作區，以及背景 Runner。主視窗包含 Collections／Environments 資源樹、Request 與 Runner 工作分頁、Params／Headers／Body 編輯分頁與 Response Body／Headers 檢視。Runner 可按 Collection 順序背景執行請求、回報進度與逐項結果，並可取消後續請求；使用者仍可操作 UI。Collection 和 Environment 分別以 JSON 保存；Request 可從側欄開啟並在 Save As 時加入 Collection。預設 Project 索引位於使用者家目錄的 `.newpostman/project.json`，資源 JSON 存於同目錄下的 `collections/` 與 `environments/`。Extractor 與 Dataset 仍在規劃中。

### 使用 Collection

1. 選擇「新增 Collection」建立集合。
2. 選擇「New Request」建立請求，在 Method、URL 與 Params／Headers／Body 分頁編輯內容。
3. 選擇「Save As」，輸入既有 Collection 名稱以加入該集合，或輸入新名稱建立集合並加入 Request。
4. 在左側展開 Collection；點選 Request 可開啟工作分頁。相同 Request 再次選取時會切回已開啟的分頁。
5. 選取 Collection 中的 Request 後，可用側欄下方的上移／下移按鈕調整執行順序；按「Save」保存已存在 Request 的修改。

Project 索引以相對路徑記錄資源；Collection JSON 存放在 `collections/`，Environment JSON 存放在 `environments/`。關閉有未儲存變更的工作分頁時，可選擇儲存、放棄或取消。
