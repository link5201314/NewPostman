# Issue tracker: GitHub

本專案的 Issues 與規格使用 GitHub Issues 管理，所有操作使用 `gh` CLI，並從目前 Git remote 判斷 repository。

## 常用操作

- 建立 issue：`gh issue create --title "..." --body "..."`
- 讀取 issue：`gh issue view <number> --json number,title,body,labels,comments`
- 列出 open issues：`gh issue list --state open`
- 留言：`gh issue comment <number> --body "..."`
- 加上／移除標籤：`gh issue edit <number> --add-label "..."`／`--remove-label "..."`
- 關閉 issue：`gh issue close <number> --comment "..."`

需要建立子 issue 時，優先使用 GitHub sub-issues；若 repository 不支援，於 issue 內標記 `Part of #<parent>`。

# Issue Label使用
## 1.架構階層標籤（區分規格與子任務）
- type:epic：給大規格需求，表示需被拆解為多個任務的類型。
- type:feature：取代泛用的 enhancement，專指功能實作。
- type:task：具體的單元任務（例如設定 UI 排版、撰寫單元測試）。
## 2.模組標籤（方便篩選對應程式碼範圍）
- scope:ui：PySide6、視窗版面、事件綁定。
- scope:core：HTTPX 連線引擎、Pydantic v2 模型驗證, 相關核心邏輯。
- scope:runner：Dataset 迭代、批次執行邏輯。
## 3.Agent 協作狀態標籤（避免所有任務同時標為可執行）
- status:blocked：有相依條件未滿足，Agent 應跳過（對應目前圖中的 Blocked 狀態）。
- status:in-progress（黃色）：Agent 或人員正在開發中。
- status:ready ：前置需求已滿足、上下文完整，Agent 可直接開工。

不同類型的label可同時使用，但相同類型Label只能擇一

## Pull requests

PRs as a request surface: **no**。PR 不作為功能需求或 triage 工作項目的入口。

## 發布規則

技能要求「publish to the issue tracker」時，建立 GitHub issue。
