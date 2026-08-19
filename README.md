# 🚀 eToro 投資組合每日追蹤與分析自動化系統 (eToro Tracker)

![eToro Tracker](https://img.shields.io/badge/eToro-Tracker-10b981?style=for-the-badge&logo=etoro&logoColor=white)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)
![Playwright](https://img.shields.io/badge/Scraper-Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)
![Gemini 1.5 Flash](https://img.shields.io/badge/AI-Gemini%201.5%20Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)

每日美股收盤後自動追蹤 eToro 明星投資者（預設 **`miulatw`**）的投資組合部位變動，比對昨日與今日持股佔比，結合 **Google Gemini 1.5 Flash** 產出繁體中文調倉總結，並透過「**多管道即時推播**」與「**GitHub Pages 現代深色儀表板**」雙軌呈現。

---

## ✨ 核心特色

- 🎯 **自動追蹤與數據攔截**：使用 **Playwright** 模擬無頭瀏覽器，優先攔截 eToro 內部 API 封包，並具備 DOM Fallback 與 Mock 容錯機制。
- 🔍 **精準調倉比對引擎**：自動計算持股佔比增減量 (Δ%)，精準標記：
  - 🆕 **新開倉 (New Position)**：昨日無、今日新增之標的
  - ❌ **全數平倉 (Liquidated/Closed)**：昨日有、今日已全數出清之標的
  - 🟢 **加碼 (Increased)** / 🔴 **減碼 (Decreased)** / ⚪ **持平 (Unchanged)**
- 🤖 **Gemini 1.5 Flash 智能摘要**：傳入調倉變動明細，自動產出 100~150 字精闢的繁體中文調倉解讀與板塊觀察。
- 📲 **多管道通知分發**：
  - **Telegram Bot**（Markdown 格式與連結）
  - **LINE Notify**（圖文摘要格式）
  - **Email (SMTP)**（深色質感 HTML 表格郵件）
  - **Discord Webhook**（Rich Embed 訊息）
- 📊 **現代科技感 GitHub Pages 儀表板**：
  - **Tailwind CSS (Dark Mode)** + **Chart.js** 互動式資產佔比甜甜圈圖與變動幅度長條圖。
  - 具備即時搜尋與狀態標籤篩選功能的持股明細對照表。
- ⚙️ **完全零維護雲端運作**：透過 **GitHub Actions** 於美股收盤後 (台灣時間 05:30) 定時執行並自動 Commit & Push 部署。

---

## 📁 專案架構目錄

```
etoro/
├── .github/
│   └── workflows/
│       └── daily_tracker.yml      # GitHub Actions 每日美股收盤排程與自動部署
├── data/
│   ├── history.json               # 歷日歷史持股快照
│   └── latest.json                # 最新一日持股、變動與 AI 摘要
├── src/
│   ├── __init__.py
│   ├── scraper.py                 # Playwright 爬蟲與 API 攔截器
│   ├── analyzer.py                # 持股佔比增減/新開倉/平倉比對邏輯
│   ├── ai_summary.py              # Gemini 1.5 Flash 繁中摘要生成模組
│   ├── notifier.py                # 多管道推播模組 (LINE/TG/Email/Discord)
│   ├── build_page.py              # index.html 靜態網頁渲染器
│   └── main.py                    # 執行總入口主程式
├── templates/
│   └── index.html.jinja2          # 視覺化儀表板 Jinja2 模板
├── .env.example                   # 本地環境變數範例檔
├── requirements.txt               # 相依套件清單
├── index.html                     # 現代科技感的 GitHub Pages 儀表板
└── README.md                      # 專案說明與設定指南
```

---

## 🛠️ 本地安裝與快速測試

### 1. 安裝環境依賴

```bash
# 建議建立並啟用 Python 虛擬環境 (Python 3.10+)
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 安裝相依套件
pip install -r requirements.txt

# 安裝 Playwright 瀏覽器核心
playwright install chromium
```

### 2. 設定環境變數

複製 `.env.example` 為 `.env` 並填入您的金鑰：

```bash
cp .env.example .env
```

`.env` 關鍵欄位說明：
```ini
TARGET_USERNAME=miulatw
GEMINI_API_KEY=AIzaSy...                 # 必填 (若無則降級為規則型摘要)
PAGES_URL=https://your-user.github.io/etoro/

# 選擇性啟用通知 (至少設定一種)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=12345678
LINE_NOTIFY_TOKEN=your_token_here
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_gmail_app_password
NOTIFICATION_EMAIL=your_email@gmail.com
```

### 3. 本地除錯與執行指令

```bash
# 1. 快速離線測試 (使用 Mock 數據，不發通知，驗證比對與網頁生成)
python src/main.py --mock --no-notify

# 2. 測試單一爬蟲模組 (抓取真實 eToro 數據)
python src/scraper.py --username miulatw

# 3. 測試 AI 摘要模組
python src/ai_summary.py

# 4. 測試多管道推播模組
python src/notifier.py

# 5. 重新根據 data/latest.json 生成 index.html
python src/build_page.py

# 6. 完整執行流程 (含真實爬蟲 + AI 摘要 + 寫入資料 + 生成網頁 + 推播)
python src/main.py
```

---

## ☁️ GitHub Actions & GitHub Pages 雲端部署

### 步驟 1：建立 GitHub 儲存庫並推動程式碼

```bash
git init
git add .
git commit -m "feat: initial commit for etoro tracker"
git branch -M main
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/etoro.git
git push -u origin main
```

### 步驟 2：設定 GitHub Actions Repository Secrets

前往儲存庫的 **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**，新增以下金鑰：

| Secret 名稱 | 說明 | 是否必填 |
| :--- | :--- | :---: |
| `GEMINI_API_KEY` | Google Gemini API Key ([取得金鑰](https://aistudio.google.com/app/apikey)) | 建議填寫 |
| `PAGES_URL` | 您的 GitHub Pages 網址 (例如 `https://username.github.io/etoro/`) | 選填 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token ([@BotFather](https://t.me/BotFather)) | 選擇性啟用 |
| `TELEGRAM_CHAT_ID` | 接收訊息的 Telegram Chat ID | 選擇性啟用 |
| `LINE_NOTIFY_TOKEN` | LINE Notify Token ([LINE Notify 官網](https://notify-bot.line.me/)) | 選擇性啟用 |
| `SMTP_HOST` | SMTP 主機 (如 `smtp.gmail.com`) | 選擇性啟用 |
| `SMTP_PORT` | SMTP 埠號 (如 `587`) | 選擇性啟用 |
| `SMTP_USER` | 發信信箱帳號 | 選擇性啟用 |
| `SMTP_PASS` | 發信信箱應用程式密碼 (App Password) | 選擇性啟用 |
| `NOTIFICATION_EMAIL` | 接收調倉日報的收件信箱 | 選擇性啟用 |
| `DISCORD_WEBHOOK_URL` | Discord 頻道 Webhook URL | 選擇性啟用 |

### 步驟 3：開啟 GitHub Actions 寫入權限與 GitHub Pages

1. 前往 **Settings** -> **Actions** -> **General**：
   - 捲動至 **Workflow permissions**，選擇 **Read and write permissions**，並點擊 **Save**。
2. 前往 **Settings** -> **Pages**：
   - **Source** 選擇 **Deploy from a branch**。
   - **Branch** 選擇 `main` / `/(root)`，並點擊 **Save**。

### 步驟 4：手動測試排程工作流

前往儲存庫的 **Actions** 頁籤 -> 點選 **eToro Portfolio Daily Tracker** -> 點擊 **Run workflow** 即可手動觸發測試！

---

## 🔔 推播通知管道申請指引

### 1. Telegram Bot (最推薦)
1. 在 Telegram 搜尋 `@BotFather` 並傳送 `/newbot`，依序設定名稱與 Username 即可取得 `TELEGRAM_BOT_TOKEN`。
2. 傳送任意訊息給您的 Bot，並搜尋 `@userinfobot` 獲取您的 `TELEGRAM_CHAT_ID`。

### 2. Gmail SMTP 設定
1. 前往 Google 帳戶 -> **安全性** -> 開啟 **兩步驟驗證**。
2. 在 **應用程式密碼 (App Passwords)** 中新增一組「其他 (eToro Tracker)」，產生的 16 位密碼即為 `SMTP_PASS`。

---

## 📄 免責聲明 (Disclaimer)

本專案僅供程式開發、量化數據分析與個人研究學習使用。專案所擷取之數據源自公開網頁資訊，AI 生成之調倉總結僅為資訊統整，**不構成任何形式的投資建議、買賣推薦或金融商品操作指示**。投資有風險，請獨立評估判斷。
