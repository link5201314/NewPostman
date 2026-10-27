# 03: Collection 工作區與 Request 分頁

**What to build:** 使用者可建立並保存 Collection，在參考截圖布局的桌面工作區中瀏覽、開啟及編輯其中的 Request，以便整理可重複使用的 API 流程。

**Blocked by:**
- 01: 單次 Request 與 Response 檢視
- 02: Environment 管理與變數替換

**Status:** completed

- [x] 啟動應用程式後呈現主工作區：左側資源導覽、上方工作分頁、中央 Request 編輯區及下方 Response 區；Response 區高度可調整。
- [x] 左側導覽顯示已實作的 Collections 與 Environments；不顯示 Docs、Specs、Mocks、Toolsets、Flows 或其他未規劃項目。
- [x] Collection 可展開顯示其中 Request；選取 Request 開啟工作分頁，同一個 Collection Request 再次選取時聚焦既有分頁。
- [x] Request 工作分頁頂端顯示 Method 與 URL，Params、Headers、Body 以分頁呈現；只顯示已實作的分頁。
- [x] Response 位於 Request 編輯區下方，提供 Body 與 Headers 檢視並在收到回應後預設顯示 Body。
- [x] 使用者可建立、命名、編輯及排序 Collection 內的 Request；第一版 Collection 項目直接包含 Request 設定，不要求跨 Collection 共用引用。
- [x] Collection 以獨立 JSON 保存，Project 索引可透過相對路徑參照 Collection。
- [x] 新 Request 可透過 Save As 加入既有或新 Collection；關閉有變更的工作分頁時提供儲存、放棄與取消。
- [x] 目前作用 Environment 選單保留於主視窗右上方，Environment 管理由側欄入口開啟；此選擇不寫入 Request。
- [x] 主視窗不顯示尚未實作的 Runner、Scripts 或 Dataset 控制項；工具列 Runner 入口於 Runner 切片加入。
- [x] 使用 pytest-qt 透過使用者可見操作驗證 Collection 導覽、工作分頁聚焦、Request 編輯區、Response 分隔區及未儲存變更提示，不耦合私有 Widget 實作細節。
- [x] Collection 儲存與載入以 JSON 往返測試；HTTP Request 行為使用 HTTPX MockTransport，不呼叫外部 API。

**Completed:** 2026-10-27