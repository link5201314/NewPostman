# 領域詞彙

| 詞彙 | 定義 |
|---|---|
| **Request（請求）** | 一次 HTTP 呼叫的設定，包含方法、URL、Headers、Params、Body、腳本與回應萃取規則。 |
| **Collection（集合）** | 依明確順序排列的一組請求，供使用者組織及批次執行。第一版的請求項目直接包含請求設定，不以跨集合共用引用為目標。 |
| **Environment（環境）** | 一組命名的使用者變數，例如 Dev 或 Staging；它是執行時變數的基底設定。 |
| **Dataset（資料集）** | 以 CSV 或 JSON 表示的一組資料列；每列提供一次迭代的參數。 |
| **Data row（資料列）** | Dataset 中供單次迭代使用的 key-value 變數集合。 |
| **Iteration（迭代）** | Runner 從 Collection 第一個請求開始，使用一筆資料列依序執行完整集合的一輪。沒有 Dataset 時執行一輪。 |
| **RunContext（執行上下文）** | 單次迭代的變數狀態，包含資料列、執行期／萃取變數與所選 Environment。每輪建立新的上下文。 |
| **Runtime variable（執行期變數）** | 單次迭代期間建立或更新的變數；Extractor 寫入的值也屬於此類。 |
| **Extractor（萃取器）** | 從 HTTP 回應本文依 JSONPath 或正則規則取值，並將結果寫入執行期變數的設定。 |
| **Runner（執行器）** | 按 Collection 順序及 Dataset 迭代規則執行請求，回報進度與逐項結果的功能。 |
| **API Engine（API 引擎）** | 執行單次 HTTP 請求、建立回應摘要並套用萃取規則的核心；不負責 UI 呈現。 |

## 變數優先序

同名變數依 **Data row > Runtime/Extracted > Environment** 解析。Extractor 更新執行期變數；Data row 優先權較高，因此同名的資料列值仍會勝出。每筆資料列開始新迭代時，執行期變數重設。

## 執行語意

- 未定義的 `{{key}}` 會在送出前造成該請求失敗，不會以空字串靜默代替。
- HTTP 回應即使為 4xx/5xx，仍代表傳輸完成；第一版不以狀態碼自動判定測試通過或失敗。
- 請求、腳本或網路錯誤記錄在該項結果中，Runner 繼續處理後續項目；依賴缺失變數的請求會自行在送出前失敗。
- 有 Dataset 時每筆有效 Data row 建立新的 RunContext，Runner 從 Collection 第一個 Request 開始完整執行一輪；沒有 Dataset 時執行一輪。取消時不再啟動新 Request。
- 單次請求核心與 UI 解耦；批次請求由背景執行緒執行，透過 Qt Signals 更新 UI。
