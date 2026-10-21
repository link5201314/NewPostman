# Issue tracker：本機 Markdown

本專案的需求、規格與工作項目以 Markdown 檔案記錄於 `.scratch/`。

## 慣例

- 每項功能使用獨立目錄：`.scratch/<feature-slug>/`
- 規格文件為 `.scratch/<feature-slug>/spec.md`
- 實作工作項目分別存放於 `.scratch/<feature-slug>/issues/`，以 `01` 起始依序編號，每項工作各自一個檔案
- 每個工作項目在開頭附近使用 `Status:` 記錄狀態；需要標示可開始交由 agent 處理時，使用 `ready-for-agent`
- 討論與歷史記錄附加於檔案末尾的 `## Comments` 區段

## 發布規格或工作項目

技能要求發布到 issue tracker 時，建立對應功能目錄，並在其中新增規格或工作項目的 Markdown 檔案。

## 查找工作項目

使用者通常會提供檔案路徑或工作項目編號；依該參照讀取對應 Markdown 檔案。
