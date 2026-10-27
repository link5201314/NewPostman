# 02: Environment 管理與變數替換

**What to build:** 使用者可在桌面工作區管理並選取 Environment，透過 `{{variable_name}}` 將其變數套用至單次 Request，以便在不同環境重用同一份請求設定。

**Blocked by:** 01: 單次 Request 與 Response 檢視

**Status:** completed

- [x] 使用者可建立、命名、編輯及選擇 Environment，並管理其 key-value 變數。
- [x] 主視窗提供 Environment 資源清單與管理入口；右上方提供目前作用 Environment 的全域選單。
- [x] 切換目前 Environment 後，手動發送的 Request 使用該環境變數；不改寫 Request 設定。
- [x] Environment 以本機 JSON 保存，重新開啟後資料仍可載入。
- [x] Project 索引可用 JSON 記錄環境設定的識別資料與相對路徑。
- [x] Request 的 URL、Headers、Params 與 Body 可解析 `{{variable_name}}` 樣板。
- [x] 此切片在 Data row 與 Extractor 尚未交付前，先支援 Environment 變數解析；完整優先序於後續 Dataset／Extractor 切片完成。
- [x] 未定義變數會在發送前顯示錯誤，該 Request 不會送出。
- [x] JSON Body 在變數替換後進行解析驗證；無效內容不會送出。
- [x] 測試透過單次 Request 的外部行為驗證 Environment 讀寫、切換、替換及缺漏變數處理。
- [x] UI 只呈現可用的 Environment 清單與切換操作；尚未實作的 Collection、Dataset 等入口不以假控制項呈現。

**Completed:** 2026-10-27
