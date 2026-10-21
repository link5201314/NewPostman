# 02: Environment 變數與本機設定保存

**What to build:** 使用者可建立、選擇與保存 Environment，並在單次 Request 中以 `{{variable_name}}` 使用 Environment 變數，以便在不同環境重用請求設定。

**Blocked by:** 01: 單次 Request 與 Response 檢視

**Status:** ready-for-agent

- [ ] 使用者可建立、命名、編輯及選擇 Environment，並管理其 key-value 變數。
- [ ] Environment 以本機 JSON 保存，重新開啟後資料仍可載入。
- [ ] Project 索引可用 JSON 記錄環境設定的識別資料與相對路徑。
- [ ] Request 的 URL、Headers、Params 與 Body 可解析 `{{variable_name}}` 樣板。
- [ ] 變數解析遵循 Data row > Runtime/Extracted > Environment；本票單尚未提供 Data row 與 Extractor，需先支援 Environment 值。
- [ ] 未定義變數會在發送前顯示錯誤，該 Request 不會送出。
- [ ] JSON Body 在變數替換後進行解析驗證；無效內容不會送出。
- [ ] 測試透過單次 Request 的外部行為驗證 Environment 讀寫、切換、替換及缺漏變數處理。
