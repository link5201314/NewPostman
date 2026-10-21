# 03: Collection 順序執行與背景 Runner

**What to build:** 使用者可建立、整理並保存 Collection，再於背景啟動 Runner 依序執行其中的 Request，同時在 UI 查看即時進度與結果，而不會因 HTTP 呼叫而失去 UI 回應。

**Blocked by:**
- 01: 單次 Request 與 Response 檢視
- 02: Environment 變數與本機設定保存

**Status:** ready-for-agent

- [ ] 使用者可建立、命名、編輯及排序 Collection 內的 Request；第一版 Collection 項目直接包含 Request 設定，不要求跨 Collection 共用引用。
- [ ] Collection 以獨立 JSON 保存，Project 索引可透過相對路徑參照 Collection。
- [ ] Runner 依 Collection 順序逐一執行 Request；此階段不做平行執行，也不使用 Dataset。
- [ ] 使用者可選取 Environment 執行 Collection，所有 Request 遵循其變數解析規則。
- [ ] Runner 在 QThread 或等效 Qt 背景工作執行，不於 UI 主執行緒執行同步 HTTP 呼叫。
- [ ] Qt Signals 回報目前進度、逐項日誌與 Request 結果，並於結束時提供摘要。
- [ ] UI 在 Runner 執行期間仍能處理事件及操作，不因等待 HTTP 回應而凍結。
- [ ] 單一 Request 的錯誤被記錄為該項結果，Runner 仍繼續後續 Request；每個項目可區分傳輸錯誤與 HTTP Response。
- [ ] 測試透過 Runner 公開行為及 HTTPX MockTransport 驗證順序、結果、進度訊號與 UI 事件處理，不依賴外部 API。
