# Prompt 演進手冊

## 一、產生專案目標開始Vibe coding(以下需求使用grill-with-docs技能輸入)
我想使用 Python 與 PySide6 開發一個輕量、聚焦於「參數化與批次鏈式執行」的桌面版 API 測試工具（類似 Postman 的核心功能精簡版）。

### 1. 專案路徑
- ~/MyPostman

### 2. 核心需求範圍 (Scope)
- **不需要**：Mocks 伺服器、效能/壓力測試、協作雲端同步、複雜監控。
- **必須具備**：
  1. **API 設定與單次發送**：支援 Method、URL、Headers、Params、Body (JSON/raw)、Script(Before request、After request)，並檢視 Response (狀態碼、耗時、Headers、格式化 Body)。
  2. **Environments (環境變數)**：可切換不同環境（如 Dev, Staging），變數使用 {{variable_name}} 語法動態替換。
  3. **Collections (集合與順序排程)**：可組織 API 請求，並設定調用順序。
  4. **Post-response Extraction (變數萃取/鏈式調用)**：支援在上一支 API 回應後，透過 JSONPath 或正則萃取特定欄位（例如 `token`），自動寫入執行期變數供下一支 API 使用。
  5. **Datasets (資料驅動/參數化)**：支援載入 CSV/JSON 資料集，將每列（Row）資料注入變數。
  6. **Runner (批次執行器)**：依序執行 Collection，支援 Iteration 迴圈（搭配 Dataset），並提供即時進度條與執行結果摘要報表。

### 3. 技術棧與非同步規範
- **UI 框架**：PySide6 (Qt for Python)。
- **HTTP 引擎**：`httpx` 或 `requests`。
- **執行緒架構 (極重要)**：Runner 執行批次請求時，必須使用 `QThread` 或 QRunnable + QThreadPool 在背景執行，透過 Qt Signals 更新 UI 進度與日誌，**絕對不可阻塞主 UI 線程**。
- **儲存格式**：專案、Collection、Environment 均使用標準 JSON 本地檔案存取。

### 4. 本階段任務
請不要一次把所有 UI 程式碼全部吐出來。請先為我產出：
1. **專案目錄結構設計**（清晰分離 Models、Core/Engine、UI components、Utils）。
2. **核心資料結構 (Pydantic 或 dataclass)**：
   - RequestModel (URL, method, headers, params, body, extractors)
   - EnvironmentModel (名稱、key-value 字典)
   - CollectionModel (名稱、請求列表順序)
   - VariableEngine (負責將文字中的 {{key}} 替換為當前變數值，解析優先序：Data row > Runtime/Extracted > Environment)。
3. **HTTP 執行核心 (ApiEngine)**：單次請求的執行與變數萃取邏輯原型。

---
## 二、UI調整(以下需求使用grill-with-docs技能輸入)
實作的規格需參考實際postman的視窗佈局(參考附圖)來調整UI設計，但只做我目前專案規劃的功能實作，其他用不到的功能元件不用放進去