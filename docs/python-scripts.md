# Python Script 使用指南

在 Request 的「腳本」分頁設定執行前與執行後 Script。腳本中使用 `context` 物件存取本次執行提供的 Request、Response 與執行期變數。

## 可用介面

| 介面 | 型別 | 說明 |
|---|---|---|
| `context.request` | `RequestModel` | 本次已完成變數替換的 Request 副本。執行前 Script 可讀取或修改它；修改不會寫回已保存的 Request。 |
| `context.response` | `ResponseSnapshot \| None` | 執行後 Script 可讀取的 HTTP Response 摘要。執行前 Script 時為 `None`。 |
| `context.runtime_variables` | `dict[str, str]` | 本次執行的 Runtime variable 字典，可讀取、設定或刪除變數。值應使用字串。 |
| `context.log(message)` | 方法 | 將自訂診斷文字以 INFO 等級送至 UI 診斷區與本地日誌；訊息會標示 Request 名稱與 Script 階段。 |

### `context.request` 欄位

`context.request` 是 `RequestModel`。可用欄位如下：

| 欄位 | 型別 | 用途 |
|---|---|---|
| `id` | `UUID` | Request 識別碼 |
| `name` | `str` | Request 名稱 |
| `method` | `str` | HTTP Method |
| `url` | `str` | 本次解析後的 URL |
| `headers` | `dict[str, str]` | Request Headers |
| `params` | `dict[str, str]` | URL 查詢參數 |
| `body_mode` | `BodyMode` | Body 模式：`none`、`json` 或 `raw` |
| `body` | `str` | Request Body |
| `before_script` | `str` | 保存的執行前 Script 文字 |
| `after_script` | `str` | 保存的執行後 Script 文字 |
| `extractors` | `list[ExtractorModel]` | Request 的 Response Extractor 設定 |

執行前 Script 在 URL、Headers、Params、Body 的變數替換後執行。修改 `context.request` 會影響本次發送；修改 `context.runtime_variables` 不會重新解析本次已替換的欄位，但可供後續 Request 使用。JSON Body 會在執行前 Script 後驗證。

```python
context.request.headers["X-Trace"] = "from-script"
context.request.params["source"] = "runner"
context.runtime_variables["request_id"] = "req-123"
context.log("已準備送出 Request")
```

### `context.response` 欄位

當 Response 已收到時，`context.response` 是 `ResponseSnapshot`：

| 欄位 | 型別 | 用途 |
|---|---|---|
| `status_code` | `int` | HTTP 狀態碼；收到 4xx／5xx 仍代表已收到 Response |
| `elapsed_ms` | `float` | HTTP 呼叫耗時，單位為毫秒 |
| `headers` | `dict[str, str]` | Response Headers |
| `body_text` | `str` | Response Body 文字 |

執行後 Script 可讀取 Response 並設定供下一個 Request 使用的變數：

```python
if context.response is not None:
    context.runtime_variables["last_status"] = str(context.response.status_code)
    context.runtime_variables["response_text"] = context.response.body_text
```

## Runtime variable 的生命週期

- 在 Collection Runner 的一次執行中，各 Request 共用同一份 `context.runtime_variables`。執行前／後 Script 與成功的 Extractor 都可更新它，後續 Request 可透過 `{{variable_name}}` 讀取。
- 變數解析優先序為 **Data row > Runtime／Extracted > Environment**；有同名 Runtime variable 時，它會優先於 Environment。
- 單次手動 Send 會建立該次呼叫自己的執行上下文；其中寫入的 Runtime variable 不會跨不同 Send 保存。若要串接多個 Request，請使用 Runner 執行 Collection。
- Request 設定在替換前會複製；Script 對 `context.request` 的修改只作用於這次呼叫，不會自動保存回 Collection。

## 錯誤處理

- 執行前 Script 發生錯誤時，該 Request 不會送出；Runner 將此項記為失敗並繼續下一個 Request。
- 執行後 Script 發生錯誤時，錯誤會記錄在該項結果；Response Extractor 仍會執行。
- Script 寫入的變數值應為 `str`。未定義或非字串值可能造成後續樣板解析失敗。
- `context.response` 為 `None` 時不可直接讀取其欄位；請先檢查是否為 `None`。
- `context.log(...)` 輸出會保留在共用診斷區，直到使用者手動清除或程式結束；也會依 `logging.json` 的 `ui_level` 與 `file_level` 分別篩選。
- 請勿透過 `context.log(...)` 輸出密碼、JWT 或其他憑證。應用程式會遮蔽常見憑證格式，但無法辨識所有自訂敏感資料。

## 安全提醒

Python Script 是受信任程式碼，具備一般 Python 權限，可能讀寫本機檔案、存取環境資訊或執行其他本機操作。NewPostman **不提供安全沙箱**。只執行你信任的 Script；不要把不受信任的腳本貼入應用程式執行。

目前明確提供的腳本介面為 `context.request`、`context.response`、`context.runtime_variables` 與 `context.log(message)`。未列出的內部類別方法或實作細節不保證維持相容；建議只依賴本指南列出的介面與行為。
