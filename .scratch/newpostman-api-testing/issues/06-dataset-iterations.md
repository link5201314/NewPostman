# 06: Dataset 導覽與批次迭代

**What to build:** 使用者可從工作區載入 CSV 或 JSON Dataset，選擇是否用於 Runner，並讓每筆資料列驅動一輪完整 Collection，以便進行隔離且可重現的參數化批次執行。

**Blocked by:** 05: Python Script 與 Response 萃取鏈

**Status:** ready-for-agent

- [ ] 側欄提供 Dataset 資源入口，顯示目前 Project 可用的資料集；不顯示未支援的資料資源管理功能。
- [ ] Project 以相對路徑記錄已載入的 Dataset，重新開啟時可找到資料來源；不複製或改寫 Dataset 原始內容。
- [ ] Runner 工作分頁提供可選 Dataset 設定；未選 Dataset 時執行一輪，有選取時依資料列迭代。
- [ ] Dataset 選擇器只在 Dataset 載入與驗證功能可用時呈現，不以空白或假控制項佔位。
- [ ] 使用者可載入 CSV Dataset，第一列作為欄名，每一筆後續資料列成為一個 Data row。
- [ ] 使用者可載入 JSON 物件陣列 Dataset，每個物件成為一個 Data row。
- [ ] 每筆 Data row 建立獨立 RunContext，依 Data row > Runtime/Extracted > Environment 優先序解析變數。
- [ ] 每個 Iteration 都從 Collection 第一個 Request 開始，並依序執行至最後一個 Request。
- [ ] 切換至下一個 Iteration 時 Runtime variables 重設；Data row 值不會被 Extractor 覆蓋。
- [ ] 有 Dataset 時執行次數與有效資料列數一致；進度及摘要包含 Iteration 和 Request 結果。
- [ ] CSV/JSON 格式錯誤或無效資料在開始執行前顯示可理解錯誤，不會造成 UI 當機。
- [ ] 透過多列暫存 Dataset 與 HTTPX MockTransport 驗證 Iteration 數量、變數隔離、鏈式請求、進度、取消及摘要，不發出真實網路請求。