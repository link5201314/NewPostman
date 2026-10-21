# 05: CSV／JSON Dataset 批次迭代

**What to build:** 使用者可載入 CSV 或 JSON Dataset，讓 Collection 以每一列資料執行一次完整 Iteration，並查看批次進度與結果摘要，必要時取消後續工作。

**Blocked by:**
- 04: Python Script 與 Response 萃取鏈

**Status:** ready-for-agent

- [ ] 使用者可載入 CSV Dataset，第一列作為欄名，每一筆後續資料列成為一個 Data row。
- [ ] 使用者可載入 JSON 物件陣列 Dataset，每個物件成為一個 Data row。
- [ ] 每筆 Data row 建立獨立 RunContext，依 Data row > Runtime/Extracted > Environment 優先序解析變數。
- [ ] 每個 Iteration 都從 Collection 第一個 Request 開始，並依序執行至最後一個 Request。
- [ ] 切換至下一個 Iteration 時 Runtime variables 重設；Data row 值不會被 Extractor 覆蓋。
- [ ] 無 Dataset 時 Collection 執行一次；有 Dataset 時執行次數與有效資料列數一致。
- [ ] Runner 持續回報 Iteration 與 Request 進度、逐項結果，並在完成時提供批次摘要。
- [ ] 使用者取消執行時 Runner 不再啟動新 Request，並安全完成或等待目前中的 Request 後回報取消狀態。
- [ ] CSV/JSON 格式錯誤或無效資料在開始執行前顯示可理解錯誤，不會造成 UI 當機。
- [ ] 透過多列暫存 Dataset 與 HTTPX MockTransport 驗證 Iteration 數量、變數隔離、鏈式請求、進度、取消及摘要，不發出真實網路請求。
