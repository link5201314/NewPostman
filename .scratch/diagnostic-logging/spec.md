# 診斷日誌

## 目標

讓使用者能從共用 UI 診斷區與本地日誌檔確認 Request、Script、Runner 與應用程式例外的執行情況，並避免把舊 Response 誤認成最新結果。

## 已確認決策

- 使用 Python logging；Script 以 `context.log(message)` 寫出使用者自訂日誌，預設等級為 INFO。
- 共用診斷面板呈現應用程式、HTTP、Script 與 Runner 日誌；Runner 原有進度紀錄保留。
- 診斷面板記錄在應用程式執行期間持續累積，可手動清除；Send 或 Runner 啟動不自動清除。
- 每筆日誌保留時間、等級、logger 名稱與原訊息；Script 訊息附加 Request 名稱與 Before／After 階段。
- 使用使用者設定目錄的 `logging.json`，分別設定 `ui_level` 與 `file_level`；設定變更於下次啟動生效。
- 支援 DEBUG、INFO、WARNING、ERROR、CRITICAL；預設 UI=INFO、檔案=DEBUG。
- 本地日誌使用輪替檔案，單檔 5 MiB，保留 3 個備份。
- 一般日誌遮蔽常見憑證欄位；不自動記錄完整 Request／Response Body。明確呼叫 `context.log(...)` 的內容由使用者負責不輸出憑證。
- 新 Request 開始時保留舊 Response 並標示其為上一筆；若本次失敗，標示本次未收到新 Response。

## 非目標

- 不新增固定格式的 Response Body／特定欄位檢視器。
- 不提供執行期間動態修改 log level 的設定 UI。
- 不記錄完整 HTTP Headers、Request Body 或 Response Body。
