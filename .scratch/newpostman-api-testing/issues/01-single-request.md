# 01: 單次 Request 與 Response 檢視

**What to build:** 使用者可在桌面應用程式建立並設定單一 Request、送出 HTTP 呼叫，並檢視完整的基本 Response 資訊，以便單獨測試 API。

**Blocked by:** None (can start immediately)

**Status:** in-progress

- [x] 使用者可設定 HTTP Method、URL、Headers、Params，以及 none、JSON 或 raw Body。
- [x] 有效的 JSON Body 可送出；JSON 格式錯誤會在發送前顯示錯誤，且不會送出請求。
- [x] 使用者可發送單一 Request，檢視 Response 狀態碼、耗時、Headers 與 Body。
- [x] JSON Response Body 以格式化內容呈現；非 JSON Response 可查看原始文字。
- [x] 收到 HTTP 4xx/5xx 時仍顯示 Response，不將其等同網路傳輸錯誤或自動判定測試失敗。
- [x] HTTP 傳輸錯誤以可理解的錯誤資訊呈現，且不使桌面應用程式當機。
- [x] 測試透過 HTTPX MockTransport 驗證送出內容及使用者可觀察結果，不呼叫外部服務。

**Completed:** 2026-10-27
