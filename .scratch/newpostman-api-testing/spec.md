Status: ready-for-agent

# NewPostman 核心 API 測試功能規格

## Problem Statement

使用者需要一個本機桌面 API 測試工具，用來建立、發送及整理 HTTP 請求，並能將回應資料帶入後續請求及批次執行。專案已完成基本單次 Request 與 Response 檢視，但目前介面仍是單一表單，缺少參考附圖所示的資源導覽、工作分頁及上下分割的編輯／回應工作區；Collections、Environment、Dataset 與 Runner 等功能也仍待實作。使用者希望借用 Postman 截圖的資訊區域安排，而非複製不在本專案範圍內的產品功能。

## Solution

建立以 Python 與 PySide6 為 UI、HTTPX 為 HTTP 引擎的本機桌面 API 測試工具。主視窗參考附圖採用左側資源導覽、上方工作分頁、中央 Request 編輯區及下方 Response 區。側欄僅呈現本專案規劃的 Collections、Environments 與 Datasets；不複製 Postman 中未納入範圍的功能。使用者可單次發送 Request，透過 Environment、Dataset 與 Extractor 管理變數，並依序執行 Collection。Runner 在背景執行緒工作，以 Qt Signals 回報進度、日誌及結果，使 UI 保持回應。Project、Collection 與 Environment 使用本機 JSON 儲存；Dataset 使用 CSV 或 JSON 檔案。

第一階段聚焦參數化與批次鏈式執行，不實作 Mocks、壓力測試、雲端協作或複雜監控。

## User Stories

1. 作為 API 使用者，我想建立 Request 並設定 HTTP Method 與 URL，以便發送不同類型的 API 呼叫。
2. 作為 API 使用者，我想編輯 Request Headers 與 URL Params，以便提供驗證資訊及查詢條件。
3. 作為 API 使用者，我想撰寫 JSON Body，並在發送前驗證其格式，以便避免送出無效 JSON。
4. 作為 API 使用者，我想撰寫 raw Body，以便發送非 JSON 格式的內容。
5. 作為 API 使用者，我想單次發送 Request，並檢視回應狀態碼、耗時、Headers 與本文，以便快速確認 API 行為。
6. 作為 API 使用者，我想查看格式化後的 JSON 回應本文，並在回應不是 JSON 時仍能查看原始文字，以便閱讀不同格式的回應。
7. 作為 API 使用者，我想在 Request 欄位使用 `{{variable_name}}` 樣板，以便重用同一份設定呼叫不同環境或資料。
8. 作為 API 使用者，我想建立多個 Environment 並在執行前選擇其中一個，以便切換 Dev、Staging 等環境設定。
9. 作為 API 使用者，我想編輯 Environment 的 key-value 變數，以便集中管理環境 URL、認證資料及其他環境參數。
10. 作為 API 使用者，我想依 Data row > Runtime/Extracted > Environment 的優先序解析同名變數，以便本輪資料列參數不被環境值或萃取值覆蓋。
11. 作為 API 使用者，我想在變數未定義時於發送前收到清楚錯誤，並確保該 Request 不會送出，以便避免錯誤呼叫服務。
12. 作為 API 使用者，我想將多個 Request 依序組織為 Collection，以便保存可重複執行的 API 流程。
13. 作為 API 使用者，我想調整 Collection 中 Request 的順序，以便安排前置登入、資料建立與後續查詢等步驟。
14. 作為 API 使用者，我想設定 Before request Script，以便在發送前動態修改已解析的 Request 或執行期變數。
15. 作為 API 使用者，我想設定 After request Script，以便讀取 Response 並準備後續流程需要的執行期資料。
16. 作為 API 使用者，我想在使用 Python Script 前看到明確的信任與安全警告，以便了解腳本可執行一般 Python 能力並可能存取本機檔案。
17. 作為 API 使用者，我想在 Before request Script 發生錯誤時看到錯誤且不發送該 Request，以便避免送出未完成設定的請求。
18. 作為 API 使用者，我想在 After request Script 發生錯誤時看到錯誤，同時仍執行 Response Extractor，以便後續請求仍可取得可萃取的資料。
19. 作為 API 使用者，我想用 JSONPath 從 Response Body 萃取欄位並寫入 Runtime variable，以便將登入回應的 token 提供給下一個 Request。
20. 作為 API 使用者，我想用正則表達式從 Response Body 擷取值，並可指定捕獲群組，以便處理非 JSON 回應或特殊文字格式。
21. 作為 API 使用者，我想讓 JSONPath 多筆匹配時採用第一筆結果，正則預設擷取第一個捕獲群組，以便萃取行為一致且可預期。
22. 作為 API 使用者，我想在 Extractor 未匹配或解析失敗時看到警告，且既有變數不被覆寫，以便判斷鏈式流程的資料狀態。
23. 作為 API 使用者，我想載入以 CSV 第一列欄名定義欄位的 Dataset，以便以表格資料參數化請求。
24. 作為 API 使用者，我想載入由 JSON 物件陣列構成的 Dataset，以便使用巢狀或較豐富的測試資料。
25. 作為 API 使用者，我想讓 Dataset 每列建立一個 Iteration，且每個 Iteration 都從 Collection 第一個 Request 重新開始，以便批次測試多組輸入資料。
26. 作為 API 使用者，我想在每個 Iteration 使用新的 RunContext，讓 Runtime variable 在下一列重設，以便不同資料列的鏈式資料互不污染。
27. 作為 API 使用者，我想讓沒有 Dataset 的 Collection 執行一次，以便直接執行一般流程。
28. 作為 API 使用者，我想在背景執行緒啟動 Runner 並看到即時進度、逐項日誌與完成摘要，以便執行批次任務時仍可操作 UI。
29. 作為 API 使用者，我想讓 Runner 依 Collection 順序序列執行 Request，以便前一個 Response 的萃取值可供下一個 Request 使用。
30. 作為 API 使用者，我想在網路錯誤、變數解析錯誤或腳本錯誤後看到該項失敗並繼續後續項目，以便一次取得完整批次結果。
31. 作為 API 使用者，我想讓 HTTP 4xx/5xx Response 保留狀態碼及回應內容，並與傳輸錯誤區分，以便診斷服務端回應；第一版不將狀態碼自動視為測試通過或失敗。
32. 作為 API 使用者，我想將 Project 索引、Collection 與 Environment 儲存為本機 JSON，以便重開應用程式後繼續使用設定。
33. 作為 API 使用者，我想讓 Project 以相對路徑參照獨立的 Collection、Environment 與 Dataset 檔案，以便搬移整個專案資料夾。
34. 作為 API 使用者，我想在 JSON 檔案缺少必要欄位或型別不符時收到指出檔案與欄位的驗證錯誤，以便修復資料而非遭遇靜默損毀。
35. 作為 API 使用者，我想取消正在執行的 Runner，讓它停止排入新的 Request 並安全結束目前工作，以便控制長時間批次工作。
36. 作為 API 使用者，我想在左側導覽中查看 Collections、Environments 與 Datasets，以便從單一工作區找到本專案支援的資源。
37. 作為 API 使用者，我想展開 Collection 查看其中依序排列的 Request，並選擇 Request 開啟工作分頁，以便快速切換與編輯流程中的請求。
38. 作為 API 使用者，我想在主視窗右上方切換目前 Environment，以便手動發送 Request 與執行 Runner 時使用同一個工作階段環境設定，而不改寫 Request 設定。
39. 作為 API 使用者，我想在工作分頁中切換 Params、Headers、Body 與 Scripts 編輯區，以便在有限畫面中專注編輯目前需要的 Request 設定。
40. 作為 API 使用者，我想將 Method 與 URL 保持在 Request 編輯區上方，以便快速辨識及調整請求目的地與類型。
41. 作為 API 使用者，我想在 Request 編輯區下方查看 Response，並拖曳分隔線調整上下區域高度，以便同時檢查請求內容與回應結果。
42. 作為 API 使用者，我想切換 Response 的 Body 與 Headers 檢視，以便在格式化／原始本文和回應標頭間快速查看。
43. 作為 API 使用者，我想由工具列的 Run 開啟 Runner 工作分頁，設定 Collection、Environment 與可選 Dataset，再開始或取消執行，以便沿用相同工作區操作批次流程。
44. 作為 API 使用者，我想讓同一個 Collection Request 再次開啟時切回既有工作分頁，以便避免重複編輯副本造成內容不一致。
45. 作為 API 使用者，我想以 Save As 將新 Request 加入既有或新 Collection，並在關閉有未儲存變更的工作分頁時選擇儲存、放棄或取消，以便明確管理請求設定。
46. 作為 API 使用者，我想只看到本專案已規劃功能的導覽與操作入口，以便介面簡潔且不被不支援功能誤導。

## Implementation Decisions

- 桌面 UI 使用 PySide6；HTTP 請求使用 HTTPX；核心資料模型使用 Pydantic v2。
- Models 定義 Request、Extractor、Environment、Collection、Project、RunContext 與執行結果等資料形狀；Core 負責變數解析、單次 HTTP 執行、Dataset 載入、Collection Runner 及 JSON 儲存；UI 元件與 Core 分離；Utils 僅放通用輔助功能。
- Request 支援 Method、URL、Headers、Params、Body mode（none、JSON、raw）、Before request Script、After request Script 與 Extractors。JSON Body 在變數替換後解析驗證；raw Body 原樣送出。
- VariableEngine 依 Data row > Runtime/Extracted > Environment 優先序解析 `{{key}}`。未定義變數在發送前使該項失敗；RunContext 每個 Iteration 建立一次，Runtime variable 不跨 Iteration 保留。
- Extractor 僅讀取 Response Body。JSONPath 多筆結果取第一筆；Regex 使用指定捕獲群組，預設第一個捕獲群組。未匹配或錯誤記錄警告且不覆寫既有值。
- **腳本決策遵循 ADR-0001**：Before/After Script 使用 Python，透過明確上下文介面提供 Request、Response、Runtime variables；視為使用者信任程式碼，可具備一般 Python 能力。執行前必須清楚警告，不得宣稱具有沙箱隔離。Before Script 在變數替換後執行，可修改本次解析後的 Request 與 Runtime variables；修改 Runtime variables 不會重新解析本次已替換欄位。Before Script 失敗則不發送；After Script 失敗仍執行 Extractors。JavaScript 相容性或不受信任腳本的隔離另行設計。
- Collection 直接依序包含 Request，不要求跨 Collection 共用請求引用。Runner 順序執行，不平行呼叫，以支援鏈式變數。
- Dataset 的 CSV 使用第一列作為欄名；JSON 使用物件陣列，每個物件代表一列。無 Dataset 時只有一個 Iteration。
- Project 使用索引 JSON 參照獨立 Collection、Environment JSON；Dataset 保留 CSV/JSON 原檔。優先使用相對路徑，讀取後以 Pydantic 驗證。
- Runner 透過 `QThread`（或等效的 `QRunnable + QThreadPool`）在背景執行，使用 Qt Signals 回報進度、日誌、結果摘要與完成狀態。不得在 UI 主執行緒執行同步 HTTP 請求。
- 主視窗採左側資源導覽、上方工作分頁、中央 Request 編輯區與下方 Response 區的分區布局；以使用者提供的 Postman 截圖作為資訊架構參考，不複製品牌、商標或未規劃功能。
- 導覽側欄僅顯示 Collections、Environments、Datasets。Collection 可展開顯示依序排列的 Request；選取 Request 開啟工作分頁，同一個 Collection Request 重複選取時聚焦既有分頁。
- Environment 管理入口位於側欄；目前作用中的 Environment 另由主視窗右上方全域選單表示，供手動 Request 與 Runner 共用，不寫回 Request。
- Request 工作區頂端固定呈現 Method 與 URL；設定分頁依目前功能顯示 Params、Headers、Body，Scripts 分頁在腳本功能交付時加入。未實作的分頁不可用空白或假入口佔位；不建立專用 Authorization 或非需求 Settings 分頁。
- Response 區位於 Request 編輯區下方，以可調整高度的分隔區呈現，並提供 Body 與 Headers 分頁；初次有 Response 時顯示 Body。
- Runner 由工具列 Run 開啟工作區分頁，而非新增側欄資源種類。Runner 可設定 Collection 與 Environment；Dataset 選擇器隨 Dataset 功能交付後才出現。開始、取消、進度、日誌與摘要留在 Runner 工作分頁。
- Request 儲存在 Collection 中並隨 Collection JSON 保存。Save As 可選擇既有或建立 Collection 後加入 Request；關閉含未儲存變更的分頁時提供儲存、放棄、取消選項。
- Dataset 資源入口及 Runner 的可選 Dataset 設定只在 Dataset 載入功能交付後提供。Environment、Collection、Dataset 等未完成功能不得以不可用的假控制項呈現。
- 視覺採乾淨淺色桌面 UI，只借用截圖的區域層次，不使用 Postman 品牌、專屬圖示或逐像素仿製。
- HTTP 4xx/5xx 視為已收到 Response；第一版不提供狀態碼斷言。網路錯誤及各項執行錯誤列入結果，Runner 繼續後續項目；後續 Request 若缺少變數則在送出前失敗。
- 測試接縫採 `CollectionRunner` 公開執行行為作為主要整合入口，允許注入 HTTPX MockTransport，並透過可觀察結果與 Qt Signals 驗證外部行為。

## Testing Decisions

- 好的測試驗證使用者可觀察的行為與契約，不綁定私有方法、內部資料結構或特定 Widget 實作細節。
- 主要整合測試經由 CollectionRunner 執行包含多個 Request 的 Collection，注入 HTTPX MockTransport，驗證實際送出的 URL、Headers、Params、Body、請求順序、回應摘要、變數替換、Extractor 鏈與逐項結果。
- 使用多筆 Dataset 驗證 Iteration 次數、每輪回到 Collection 起點、Runtime variable 重設及資料列優先序；另驗證無 Dataset 時僅執行一輪。
- 以 pytest-qt 從主視窗的可觀察互動驗證側欄只顯示已規劃資源、Collection Request 開啟與重複聚焦分頁、Environment 全域切換、Request／Response 分頁與分隔區、Runner 工作分頁及未儲存變更提示；不依賴私有 Widget 實作細節。
- 保持已確認的主要整合接縫：透過 CollectionRunner 公開執行行為並注入 HTTPX MockTransport，驗證批次端到端請求行為；Qt UI 測試只補足使用者可見的布局與操作契約。
- 以 Qt 測試事件迴圈與 Signals 驗證 Runner 於背景執行、持續發送進度／日誌、完成後產生摘要，且 UI 執行緒仍能處理事件；避免以時間敏感或任意 sleep 的方式判定非阻塞。
- 覆蓋變數缺漏、JSON Body 無效、HTTP 傳輸失敗、4xx/5xx Response、Before/After Script 例外、Extractor 未匹配與格式錯誤等情境，確認錯誤分類、是否發送及 Runner 是否續行符合規格。
- JSON 儲存使用暫存目錄測試 Project、Collection、Environment 的往返載入與驗證錯誤；Dataset 測試使用暫存 CSV/JSON 檔案，不發出真實網路請求。
- 專案已有 pytest 與 pytest-qt 的單次 Request UI 測試，可沿用其 MockTransport 與 Qt event loop 慣例；所有 HTTP 行為透過 MockTransport 控制，不依賴外部服務。

## Out of Scope

- Mock Server、效能／壓力測試、雲端協作同步及複雜監控。
- JavaScript 腳本相容、腳本沙箱、不受信任程式碼的安全隔離。
- HTTP 狀態碼斷言、可配置測試通過條件與重試政策。
- Collection 跨集合請求引用、平行執行及跨 Iteration 保留 Runtime variable。
- 專用 OAuth 或其他複雜認證流程介面；第一版可使用 Headers 與 Params 設定。
- 完整的匯入／匯出交換格式相容性及雲端專案管理。
- 複製 Postman 全產品介面或其 Docs、Specs、Mocks、Toolsets、Flows、協作等未規劃功能；亦不建立專用 Authorization 或無明確需求的 Settings 分頁。

## Further Notes

- 本規格依專案領域詞彙文件使用 Request、Collection、Environment、Dataset、Data row、Iteration、RunContext、Runtime variable、Extractor、Runner 與 API Engine 等名稱。
- Python 腳本可執行任意程式碼，是明確的信任邊界，不可用隱藏的 `exec` 限制或一般 Python 執行環境冒充沙箱。
- 使用者已確認以 CollectionRunner 為主要整合測試接縫，透過 MockTransport 檢驗請求與鏈式執行，並驗證 Qt Signals 和 UI 非阻塞行為。
- 使用者已確認採用截圖參考布局的建議：左側只列規劃中的資源，上方工作分頁、Request/Response 上下分區、全域 Environment 選單、工具列 Runner 分頁，以及以 Collection 儲存 Request；重複 Request 聚焦既有分頁。
