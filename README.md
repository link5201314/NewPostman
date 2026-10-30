# NewPostman
使用 Python 與 PySide6 開發的輕量 API 測試工具，聚焦於參數化與批次鏈式執行。

## 文件

- [架構設計](docs/architecture.md)
- [核心資料模型與引擎原型](docs/core-prototype.md)
- [Python Script 使用指南](docs/python-scripts.md)
- [領域詞彙](CONTEXT.md)

## uv 開發環境

本專案使用 uv 管理 Python 版本、虛擬環境與依賴套件：

```powershell
uv sync
uv run newpostman
```

新增正式依賴：`uv add <套件名稱>`；新增開發依賴：`uv add --dev <套件名稱>`。提交 `pyproject.toml` 與 `uv.lock` 以確保環境可重現。

執行測試：

```powershell
uv run pytest
```

## 目前功能

目前已完成單次 HTTP Request 編輯與送出、Response 狀態碼／耗時／Headers／Body 檢視、Environment 管理與變數替換、Collection 工作區、背景 Runner、Python Script 與 Response Extractor 鏈式執行，以及 CSV／JSON Dataset 迭代。主視窗包含 Collections／Environments／Datasets 資源樹、Request 與 Runner 工作分頁、Params／Headers／Body／腳本編輯分頁與 Response Body／Headers 檢視。Runner 可按 Dataset 資料列從頭依序執行 Collection、回報 Iteration／Request 進度與逐項結果，並可取消後續請求；使用者仍可操作 UI。Collection 和 Environment 以 JSON 保存；Dataset 原始檔保留原位，Project 索引只記錄相對路徑。預設 Project 索引位於使用者家目錄的 `.newpostman/project.json`，資源 JSON 存於同目錄下的 `collections/` 與 `environments/`。

### 使用 Dataset 迭代 Runner

1. 選擇工具列「載入 Dataset」，載入 CSV 或 JSON 檔；資料集會列在側欄 Datasets 分類，來源檔案不會被複製或改寫。
2. CSV 第一列為欄名，後續每列是一筆 Data row；JSON 使用物件陣列，每個物件是一筆 Data row。Dataset 必須是 CSV 或 JSON，且來源檔案需保持可讀。
3. 開啟 Runner、選擇 Collection，並可選擇 Dataset。未選 Dataset 時執行一輪；選取後每筆 Data row 會各自從 Collection 第一個 Request 開始。
4. 每輪建立新的 RunContext，Runtime variable 不會帶入下一輪。變數依 Data row > Runtime／Extracted > Environment 優先序解析；Extractor 不會覆蓋同名 Data row。

Project 索引以相對路徑記錄 Dataset 來源；搬移 Project 時，請一併保持 Dataset 檔案相對於 Project 的位置，或在新 Project 中重新載入。

### 使用 Scripts 與 Extractors

在 Request 的「腳本」分頁可編輯執行前／後 Python Script，並設定 JSONPath 或 Regex Extractor。`context.request`、`context.response` 與 `context.runtime_variables` 的欄位、生命週期及範例，請參閱[Python Script 使用指南](docs/python-scripts.md)。Extractor 會從 Response Body 萃取值，供同一 Collection 後續 Request 使用 `{{variable_name}}` 引用。變數依 Data row > Runtime/Extracted > Environment 優先序解析。

**安全提醒：Python Script 是受信任程式碼，具備一般 Python 權限，可能讀寫本機檔案或執行其他本機操作。NewPostman 不提供安全沙箱；只執行你信任的 Script。**

### 使用 Collection

1. 選擇「新增 Collection」建立集合。
2. 選擇「New Request」建立請求，在 Method、URL 與 Params／Headers／Body 分頁編輯內容。
3. 選擇「Save As」，輸入既有 Collection 名稱以加入該集合，或輸入新名稱建立集合並加入 Request。
4. 在左側展開 Collection；點選 Request 可開啟工作分頁。相同 Request 再次選取時會切回已開啟的分頁。
5. 選取 Collection 中的 Request 後，可用側欄下方的上移／下移按鈕調整執行順序；按「Save」保存已存在 Request 的修改。

Project 索引以相對路徑記錄資源；Collection JSON 存放在 `collections/`，Environment JSON 存放在 `environments/`。關閉有未儲存變更的工作分頁時，可選擇儲存、放棄或取消。

## Windows 可攜式打包（Nuitka）

打包會產生 Windows standalone 資料夾，目標電腦不需要安裝 Python 或 uv。請在 Windows x64 的專案根目錄執行；需先安裝 Nuitka 支援的 C 編譯器，建議使用 Visual Studio Build Tools 的「使用 C++ 的桌面開發」工作負載與 Windows SDK。打包使用 `--lto=yes`，因此編譯器／連結器也必須支援 LTO。

```powershell
uv sync
uv run python -m nuitka --standalone --enable-plugin=pyside6 --lto=yes --windows-console-mode=disable --output-dir=dist --output-filename=NewPostman.exe newpostman
```

成功後，輸出結構如下（Nuitka 可能在資料夾內另外產生 Qt 外掛、Python 執行期與相依 DLL）：

```text
dist/
└── newpostman.dist/
	├── NewPostman.exe
	├── *.dll
	├── PySide6/
	└── ...
```

最後還要簽署應用程式(必須要有安裝Windows SDK)
```powershell
signtool sign /fd sha256 /n IsaacTestApp /tr http://timestamp.digicert.com /td sha256 "D:\PythonProjects\NewPostman\dist\newpostman.dist\NewPostman.exe"
```

將整個 `NewPostman.dist` 資料夾複製到另一台相容的 Windows x64 電腦，再執行其中的 `NewPostman.exe`。不可只複製 exe；同資料夾中的 DLL 與 Qt 支援檔都是執行所需。每次重新打包前可先刪除舊的 `dist/`，避免混入上次產物。


### 資料與路徑注意事項

- 應用程式沒有依賴目前工作目錄或程式旁的相對資源路徑；PySide6 外掛由 Nuitka 外掛一併收集。
- Project 預設儲存在使用者家目錄的 `.newpostman/project.json`（Windows 通常是 `%USERPROFILE%\.newpostman\project.json`），Collection 與 Environment 也保存在該 Project 下。因此打包的程式可搬移，但使用者資料不會自動跟著程式資料夾移動；需要搬移資料時，請另外複製 `.newpostman` 或使用應用程式所指向的 Project。
- Dataset 原始檔不會複製到 Project；索引以相對 Project 根目錄的路徑保存。搬移 Project 時須維持 Dataset 的相對位置，或在新電腦重新載入 Dataset。
- 使用者 Python Script 是執行期動態執行；若 Script 匯入打包時未收錄的第三方套件，請將該套件納入建置設定並重新打包。不要假設目標電腦已安裝的 Python 套件可供此程式使用。
- 此命令不進行程式簽署。完成打包後再依發行流程使用 Windows SDK 的 `signtool` 簽署；未簽署程式可能出現 SmartScreen 或安全軟體警告。
- 建置需在目標作業系統與架構上進行；Windows 版產物不是 macOS／Linux 執行檔。打包時需網路連線的 API 仍需要目標電腦可連線。
