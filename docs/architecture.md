# NewPostman 架構設計

## 目標與範圍

NewPostman 是以 Python、PySide6 建立的本機桌面 API 測試工具，聚焦於參數化請求、回應萃取與依序批次執行。第一階段涵蓋單次 HTTP 呼叫、Environment、Collection、CSV/JSON Dataset、Before/After Script、回應檢視與 Runner 的核心設計；不包含 Mocks、壓力測試、雲端協作或複雜監控。

本文件記錄整體目標架構及模組責任。已實作單次 Request、HTTP 傳送與 Response 檢視、Environment JSON 管理與變數替換、Collection JSON 管理和 Request 工作區、背景 Collection Runner、Python Script 與 Response Extractor 鏈式執行，以及 CSV／JSON Dataset 迭代。

Before/After Script 使用 Python 並視為受信任程式碼的決策，詳見 `docs/adr/0001-python-request-scripts.md`。

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

目前已實作 Request、Extractor、Dataset、RunContext、Environment 與 Collection Models、API Engine、DatasetLoader、ScriptEngine、ResponseExtractor、ProjectStore、VariableEngine、CollectionRunner、單次請求、Collection 工作區、Runner 工作分頁、Scripts 編輯器、Dataset 導覽與 Environment 管理 UI。測試使用 pytest 與 pytest-qt。

## 模組責任

- **Models**：使用 Pydantic v2 定義 Request、Extractor、RunContext、Environment、Collection、Project 與執行結果。負責欄位型別、預設值與 JSON 資料驗證，不包含 HTTP 或 UI 行為。
- **Core / Engine**：`VariableEngine` 依 Data row > Runtime/Extracted > Environment 優先序解析樣板；`ScriptEngine` 執行具一般 Python 權限的受信任使用者 Script；`ResponseExtractor` 從 Response Body 依 JSONPath 或 Regex 擷取變數；`ApiEngine` 執行單次同步 HTTP 呼叫；Dataset Loader 載入 CSV/JSON；Collection Runner 管理迭代、順序、結果與進度；Storage 負責 JSON 本機檔案讀寫。
- **UI components**：PySide6 Widgets 呈現請求編輯、集合、環境、回應與 Runner 狀態。UI 僅呼叫 Core 服務，不自行實作 HTTP 或變數解析。
- **Utils**：放置跨模組且不具領域狀態的通用工具，如 JSON 格式化與錯誤呈現輔助。
- **Tests**：以可注入的 HTTPX Client 測試引擎，避免單元測試必須連外網。

## 主視窗布局與操作邊界

主視窗參考使用者提供的 Postman 截圖安排資訊區域，但不複製其品牌或未規劃功能。採左側資源導覽、上方工作分頁、中央 Request 編輯區及下方 Response 區；上下區以可調整高度的分隔區分開。視覺採乾淨淺色桌面樣式。

- 導覽側欄僅呈現 Collections、Environments、Datasets。Collection 可展開顯示 Request，點選後開啟其工作分頁；再次開啟相同 Collection Request 時聚焦既有分頁。
- Collection 內 Request 可由側欄上移／下移調整順序，並將新順序保存回 Collection JSON。
- Environment 的管理入口在側欄；主視窗右上方另設目前作用 Environment 選單，供手動發送與 Runner 共用。選擇 Environment 不會改寫 Request。
- Request 工作區頂端顯示 Method 與 URL；設定分頁顯示 Params、Headers、Body 與 Scripts。Scripts 分頁提供 Before/After Python Script、Response Extractor 與常駐信任邊界提醒。未實作功能不得以空白或假入口佔位；不設專用 Authorization 或非需求 Settings 分頁。
- Response 位於編輯區下方，提供 Body 與 Headers 檢視；收到回應後預設顯示 Body。
- Response 保留上一筆結果時需標示其新舊狀態；新的請求開始或失敗不得讓舊內容看起來像本次回應。
- 主視窗底部提供共用診斷日誌 Dock，累積應用程式、Script 與 Runner 訊息，並提供手動清除；診斷日誌不取代 Runner 的進度檢視。
- Runner 由工具列 Run 開啟為工作分頁，不是側欄資源。Runner 選擇 Collection、作用 Environment 與可選 Dataset；未選 Dataset 時執行一輪，選取後每筆 Data row 各執行一輪完整 Collection。
- Request 隨 Collection JSON 儲存。新 Request 使用 Save As 加入既有或新 Collection；既有 Request 可直接儲存更新。關閉有未儲存變更的工作分頁時提供儲存、放棄與取消。
- Postman 截圖只作為區域層次的參考，不逐像素仿製，亦不加入 Docs、Specs、Mocks、Toolsets、Flows 等未規劃功能。

此布局決策按垂直切片落實：單次請求先提供 Request/Response 功能；Environment 切片加入 Environment 資源清單、管理入口及全域選單；Collection 工作區切片補上完整主視窗、Collection 導覽與 Request 分頁；Runner 以後續獨立切片加入工作分頁與背景執行；Scripts 與 Dataset 入口隨各自功能交付後加入，避免顯示未完成的控制項。

## JSON 持久化

採用 Project 索引及獨立資源來源：`project.json` 記錄 Collection、Environment 的識別名稱及相對路徑；每個 Collection 與 Environment 各自存成 JSON。Dataset 保留使用者的 CSV／JSON 原始檔，Project 索引僅以相對路徑登錄，不複製或改寫內容。搬移 Project 時需維持 Dataset 相對位置，或重新載入來源。讀取 Dataset 時驗證格式與列資料；錯誤需指出檔案及資料列，不得靜默丟棄無效內容。

## 變數生命週期與優先序

每個 Iteration 建立一個 RunContext：

1. Environment 提供環境基底值。
2. Dataset 的目前資料列覆蓋同名 Environment 值。
3. 執行期／Extractor 值覆蓋 Environment 值，但不覆蓋 Data row。
4. Extractor 寫入同名執行期變數時採最新萃取值；跨至下一個資料列時重設執行期變數。

解析模板 `{{key}}` 時，依 **Data row > Runtime/Extracted > Environment** 查找。未定義變數會在送出前使該請求失敗。第一版將變數插值視為文字替換；JSON Body 完成替換後再解析，若產生無效 JSON 則不送出。

## 單次請求流程

1. 以 RunContext 建立變數解析器，將模板套用至 URL、Headers、Params、Body。
2. 複製 Request 設定後執行 Before request Script；腳本可讀取／修改已解析的 Request 與執行期變數。此時修改變數不會重新套用到本次請求已解析的欄位，會影響後續請求。
3. 驗證 JSON Body；失敗則在發送前回報錯誤。
4. 透過 HTTPX 發送請求，記錄耗時、狀態碼、Headers 與本文。收到 4xx/5xx 是傳輸完成，狀態碼不自動等同測試失敗。
5. 若有 HTTP 回應，執行 After request Script。若此腳本錯誤，記錄錯誤但仍嘗試 Extractors。
6. 依設定順序萃取回應本文：JSONPath 多筆只取第一筆；正則取第一個擷取群組。未匹配或解析失敗時記錄警告，不覆寫既有變數。
7. 回傳結構化單次執行結果，供 UI 或 Runner 呈現。

腳本使用 Python 並視為受信任程式碼，可使用一般 Python 能力，包括存取本機檔案；不具安全沙箱。Scripts 分頁常駐顯示警告，單次 Request 及 Runner 開始執行含 Script 的工作前也會顯示提醒。Before Script 出錯時不送出請求。網路錯誤、模板解析錯誤及腳本錯誤均記錄在單項結果，Runner 繼續後續請求；After Script 出錯仍會執行 Extractors。Runtime variable 與 Extractor 值在單次 Collection Runner 執行中共用，供後續 Request 解析。

## Runner 與 Qt 執行緒

`ApiEngine` 維持同步、Qt 無關，方便單元測試及單次送出。`CollectionRunner` 在 `QThread` 背景執行：沒有 Dataset 時使用一筆空 Data row 執行一輪；有 Dataset 時，每列建立新的 RunContext 並從 Collection 第一個 Request 開始，請求依序呼叫 `ApiEngine`。Runtime variable 每輪重設，Data row 優先於 Runtime／Extractor 及 Environment。透過 Qt Signals 回報整體及 Iteration／Request 進度、逐項日誌、Request 結果、完成摘要與取消狀態；禁止在 UI 主執行緒執行同步 HTTP 呼叫。取消會阻止下一個 Request 啟動，並等待目前同步 HTTP 呼叫安全完成。

第一版不平行執行請求，以保證萃取變數可供下一個請求使用。使用者取消時，Runner 應停止排入新請求並安全結束目前工作；取消語意可在 Runner 實作階段再細化。

## 診斷日誌

應用程式以 Python logging 記錄 HTTP 摘要、執行錯誤、Extractor 警告、Runner 活動及 Script 明確呼叫的 `context.log(...)`。`LoggingService` 從使用者設定目錄的 `logging.json` 載入 `file_level` 與 `ui_level`，各自篩選輪替檔案與共用 UI 診斷面板；預設檔案為 DEBUG、UI 為 INFO。檔案上限 5 MiB，保留 3 個備份。UI 訊息透過 Qt Signal 從背景 Runner 執行緒轉送，不直接操作 Widget。一般日誌不得輸出完整 Request／Response 本文，且需遮蔽常見憑證欄位。

## 未納入第一階段

- HTTP 狀態碼斷言、測試通過條件與重試政策。
- 腳本沙箱、JavaScript 執行環境與雲端同步。
- Collection 跨集合引用、平行執行、效能測試及 Mock Server。
- 身分驗證的專用 UI；第一版可透過 Headers／Params 表達。
