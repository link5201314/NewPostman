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

## Pull requests

PRs as a request surface: **no**。PR 不作為功能需求或 triage 工作項目的入口。

## 發布規則

技能要求「publish to the issue tracker」時，建立 GitHub issue。
