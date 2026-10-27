# 04: 背景 Runner 工作分頁

**What to build:** 使用者可從工具列開啟 Runner 工作分頁，設定 Collection 與 Environment，並在背景依序執行請求、查看進度和摘要，而不會讓桌面 UI 停止回應。

**Blocked by:** 03: Collection 工作區與 Request 分頁

**Status:** completed

- [x] 工具列的 Run 開啟 Runner 工作分頁；Runner 不列為左側資源種類。
- [x] Runner 可選擇 Collection，並使用目前作用 Environment；此票單尚不提供 Dataset 選擇器或 Iteration。
- [x] Runner 依 Collection 順序逐一執行 Request，不平行呼叫。
- [x] Runner 在 QThread 或等效 Qt 背景工作執行，不於 UI 主執行緒執行同步 HTTP 呼叫。
- [x] Qt Signals 回報進度、逐項日誌、Request 結果與完成摘要；UI 在執行期間仍能處理事件及操作。
- [x] 使用者可取消 Runner；取消後不啟動新 Request，並安全等待或結束目前中的 Request。
- [x] 單一 Request 的錯誤記錄在該項結果，Runner 繼續後續 Request；HTTP 4xx/5xx Response 與傳輸錯誤清楚區分。
- [x] 透過 Runner 公開執行行為及注入的 HTTPX MockTransport 驗證順序、結果、進度訊號與取消，不呼叫外部 API。
- [x] 以 pytest-qt 驗證 Runner 工作分頁操作及執行期間 UI 仍可回應，不以私有實作細節或不穩定的固定延遲作為測試依據。

**Completed:** 2026-10-27