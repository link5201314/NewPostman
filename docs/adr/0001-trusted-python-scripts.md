# 將 Request Scripts 視為受信任的 Python 程式碼

NewPostman 第一版使用 Python 執行 Before request 與 After request scripts，並將腳本視為使用者明確提供且受信任的本機程式碼，不提供安全沙箱隔離。選擇此方式可讓腳本直接操作明確提供的 Request、Response 與執行期變數，同時避免第一版引入額外腳本執行環境與隔離機制；代價是腳本可能使用 Python 一般能力（例如存取本機檔案），因此 UI 必須在編輯或執行前清楚警告使用者，且不得暗示腳本可安全執行於不受信任來源。若未來需要分享或執行不受信任的 Collection，必須先重新評估此決策並設計安全隔離，不可僅靠限制 `exec` globals 宣稱具備沙箱安全性。
