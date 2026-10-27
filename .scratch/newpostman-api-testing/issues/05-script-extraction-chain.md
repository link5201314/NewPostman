# 05: Python Script 與 Response 萃取鏈

**What to build:** 使用者可在 Collection 的 Request 上執行 Before/After Python Script，並從 Response 萃取資料作為 Runtime variable，供後續 Request 使用，完成可觀察的鏈式 API 流程。

**Blocked by:** 04: 背景 Runner 工作分頁

**Status:** ready-for-agent

- [ ] Request 工作分頁提供 Scripts 分頁以編輯 Before request 與 After request Script；在此功能交付前不顯示空白 Scripts 分頁。
- [ ] Before request Script 可在變數替換後執行，讀取及修改本次解析後的 Request 與 Runtime variables；修改 Runtime variables 不會重新解析本次已替換欄位。
- [ ] After request Script 可讀取已收到的 Response 並更新 Runtime variables。
- [ ] 使用 Python Script 前向使用者清楚說明腳本屬受信任程式碼，可能執行一般 Python 能力並存取本機檔案；不得宣稱有安全沙箱。
- [ ] Before request Script 發生錯誤時，該 Request 不送出，錯誤納入逐項結果，Runner 繼續後續項目。
- [ ] After request Script 發生錯誤時記錄錯誤，但仍執行該 Request 的 Extractors。
- [ ] Extractor 可使用 JSONPath 或 Regex 從 Response Body 萃取資料並寫入指定 Runtime variable。
- [ ] JSONPath 多筆匹配時取第一筆；Regex 可指定捕獲群組，預設使用第一個捕獲群組。
- [ ] Extractor 未匹配或解析失敗時提供警告且不覆寫既有變數；最新成功萃取值更新同名 Runtime variable。
- [ ] Collection 中後續 Request 可透過 `{{variable_name}}` 使用前面成功萃取的值；以 MockTransport 驗證實際鏈式請求內容。
- [ ] 變數完整優先序維持 Data row > Runtime/Extracted > Environment；Data row 的端到端驗證於 Dataset 票單完成。
- [ ] 此決策遵循 ADR-0001；不新增 JavaScript 相容或不受信任腳本沙箱。