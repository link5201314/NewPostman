# NewPostman 架構設計

## 目標與範圍

NewPostman 是以 Python、PySide6 建立的本機桌面 API 測試工具，聚焦於參數化請求、回應萃取與依序批次執行。第一階段涵蓋單次 HTTP 呼叫、Environment、Collection、CSV/JSON Dataset、Before/After Script、回應檢視與 Runner 的核心設計；不包含 Mocks、壓力測試、雲端協作或複雜監控。

本文件先記錄架構與核心原型程式碼，不建立對應 Python 模組，也不實作 UI。

## 建議目錄結構

```text
NewPostman/
├── CONTEXT.md                    # 領域詞彙與語意
├── docs/
│   ├── architecture.md           # 架構與模組責任
│   └── core-prototype.md         # 模型、變數引擎、HTTP 核心程式原型
├── project.json                  # 專案索引與檔案參照
├── collections/
│   └── *.json                    # 各 Collection 的獨立 JSON
├── environments/
│   └── *.json                    # 各 Environment 的獨立 JSON
├── datasets/                     # 可選：專案內的 CSV/JSON 資料集
├── newpostman/
│   ├── __init__.py
│   ├── __main__.py               # `uv run newpostman` 的應用程式入口
│   ├── models/
│   │   ├── request.py
│   │   ├── environment.py
│   │   ├── collection.py
│   │   ├── project.py
│   │   └── execution.py
│   ├── core/
│   │   ├── variable_engine.py
│   │   ├── api_engine.py
│   │   ├── dataset_loader.py
│   │   ├── collection_runner.py
│   │   └── storage.py
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── request_editor.py
│   │   ├── response_view.py
│   │   ├── collection_panel.py
│   │   ├── environment_editor.py
│   │   └── runner_panel.py
│   └── utils/
│       ├── json_format.py
│       └── errors.py
└── tests/
    ├── test_variable_engine.py
    ├── test_api_engine.py
    └── test_dataset_loader.py
```

目前 `newpostman/models`、`newpostman/core`、`newpostman/utils` 已有空目錄；此結構是後續實作時的模組規劃。`ui/`、測試及資料目錄則按功能實作時新增。

## 模組責任

- **Models**：使用 Pydantic v2 定義 Request、Extractor、Environment、Collection、Project 與執行結果。負責欄位型別、預設值與 JSON 資料驗證，不包含 HTTP 或 UI 行為。
- **Core / Engine**：`VariableEngine` 統一解析模板；`ApiEngine` 執行單次同步 HTTP 呼叫與萃取；Dataset Loader 載入 CSV/JSON；Collection Runner 管理迭代、順序、結果與進度；Storage 負責 JSON 本機檔案讀寫。
- **UI components**：PySide6 Widgets 呈現請求編輯、集合、環境、回應與 Runner 狀態。UI 僅呼叫 Core 服務，不自行實作 HTTP 或變數解析。
- **Utils**：放置跨模組且不具領域狀態的通用工具，如 JSON 格式化與錯誤呈現輔助。
- **Tests**：以可注入的 HTTPX Client 測試引擎，避免單元測試必須連外網。

## JSON 持久化

採用專案索引與獨立檔案：`project.json` 記錄 Collection、Environment 的識別名稱及相對路徑；每個 Collection 與 Environment 各自存成 JSON。Dataset 保留 CSV/JSON 原始檔，專案只記錄路徑及必要設定；相對路徑優先，讓整個專案資料夾可搬移。讀檔後以 Pydantic 驗證，錯誤應指出檔名與欄位，不應靜默丟棄無效內容。

## 變數生命週期與優先序

每個 Iteration 建立一個 RunContext：

1. Environment 提供環境基底值。
2. Dataset 的目前資料列覆蓋同名 Environment 值。
3. 執行期／Extractor 值覆蓋 Environment 值，但不覆蓋 Data row。
4. Extractor 寫入同名執行期變數時採最新萃取值；跨至下一個資料列時重設執行期變數。

解析模板 `{{key}}` 時，依 **Data row > Runtime/Extracted > Environment** 查找。未定義變數會在送出前使該請求失敗。第一版將變數插值視為文字替換；JSON Body 完成替換後再解析，若產生無效 JSON 則不送出。

## 單次請求流程

1. 以 RunContext 建立變數解析器，將模板套用至 URL、Headers、Params、Body。
2. 複製 Request 設定後執行 Before request script；腳本可讀取／修改已解析的 Request 與執行期變數。此時修改變數不會重新套用到本次請求已解析的欄位，會影響後續請求。
3. 驗證 JSON Body；失敗則在發送前回報錯誤。
4. 透過 HTTPX 發送請求，記錄耗時、狀態碼、Headers 與本文。收到 4xx/5xx 是傳輸完成，狀態碼不自動等同測試失敗。
5. 若有 HTTP 回應，執行 After request script。若此腳本錯誤，記錄錯誤但仍嘗試 Extractors。
6. 依設定順序萃取回應本文：JSONPath 多筆只取第一筆；正則取第一個擷取群組。未匹配或解析失敗時記錄警告，不覆寫既有變數。
7. 回傳結構化單次執行結果，供 UI 或 Runner 呈現。

腳本使用 Python 並視為受信任程式碼，不具安全沙箱；執行前應向使用者明確告知。Before script 出錯時不送出請求。網路錯誤、模板解析錯誤及腳本錯誤均記錄在單項結果，Runner 繼續後續請求；若後續請求缺少必要變數，該請求在發送前失敗。

## Runner 與 Qt 執行緒

`ApiEngine` 維持同步、Qt 無關，方便單元測試及單次送出。Runner 在 `QThread`（或後續選用 `QRunnable + QThreadPool`）背景執行，按 Dataset 每列逐輪、Collection 內請求依序呼叫 `ApiEngine`。透過 Qt Signals 回報進度、逐項日誌、完成摘要與取消狀態；禁止在 UI 主執行緒執行同步 HTTP 呼叫。

第一版不平行執行請求，以保證萃取變數可供下一個請求使用。使用者取消時，Runner 應停止排入新請求並安全結束目前工作；取消語意可在 Runner 實作階段再細化。

## 未納入第一階段

- HTTP 狀態碼斷言、測試通過條件與重試政策。
- 腳本沙箱、JavaScript 執行環境與雲端同步。
- Collection 跨集合引用、平行執行、效能測試及 Mock Server。
- 身分驗證的專用 UI；第一版可透過 Headers／Params 表達。
