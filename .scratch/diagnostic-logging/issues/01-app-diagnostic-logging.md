# 實作可設定的應用程式診斷日誌

Status: completed

## 需求

依 `.scratch/diagnostic-logging/spec.md` 實作 logging.json 設定、分離 UI／檔案日誌等級、輪替檔案、共用診斷面板、Script context.log、Runner 與未處理例外記錄，以及 Response 新舊標示。

## 驗收條件

- 可配置 `ui_level` 與 `file_level`，預設分別為 INFO 與 DEBUG。
- 檔案日誌輪替上限 5 MiB 並保留 3 個舊檔。
- `context.log(...)` 訊息顯示 Request 名稱與 Script 階段，並依各輸出等級獨立篩選。
- Runner 訊息與應用程式錯誤可由共用診斷面板檢視；背景執行緒使用 Qt Signal 更新 UI。
- 面板內容在執行期間累積，可手動清除；執行 Request／Runner 不自動清除。
- Send 開始／失敗時清楚標示舊 Response 狀態。
- 測試涵蓋設定篩選、檔案輪替／遮蔽、Script 日誌與 UI、Runner 診斷訊息。
- README、Python Script 指南與架構文件同步更新。
