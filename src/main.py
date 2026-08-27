"""
eToro 投資組合追蹤自動化系統 - 主程式入口 (Main Orchestrator)
調度流程:
1. Playwright / SAPI 爬蟲 (抓取持倉與可用餘額)
2. 數據比對 (今日 vs 昨日，只要 diff > 0 為加碼，diff < 0 為減碼)
3. Gemini 1.5 Flash AI 摘要生成
4. 儲存最新狀態至 data/latest.json 與 data/history.json
5. 生成/更新現代深色科技感 index.html 靜態網頁 (包含 5 大 KPI 卡片與餘額資訊)
6. 發送多管道推播通知 (LINE Notify / Telegram / Email / Discord)
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# 台灣時區 (UTC+8)
TAIPEI_TZ = timezone(timedelta(hours=8))


def get_taipei_now() -> datetime:
    """取得台灣時區 (UTC+8) 的當前時間"""
    return datetime.now(TAIPEI_TZ)

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 確保當前目錄與 src 可被引用
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.scraper import EToroScraper, get_mock_portfolio_data
from src.analyzer import PortfolioAnalyzer
from src.ai_summary import generate_ai_summary
from src.notifier import NotificationDispatcher
from src.build_page import PageBuilder

# 載入 .env
load_dotenv(os.path.join(BASE_DIR, ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("eToroTracker")


def load_history_data(history_file: str) -> dict:
    """載入歷史紀錄檔案"""
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"讀取歷史檔案失敗 ({e})，重新初始化字典。")
    return {}


def get_latest_yesterday_portfolio(history: dict, today_str: str) -> list:
    """從歷史紀錄中找出前一個交易日的持股快照"""
    sorted_dates = sorted([d for d in history.keys() if d < today_str], reverse=True)
    if sorted_dates:
        latest_prev_date = sorted_dates[0]
        logger.info(f"找到前次歷史快照日期: {latest_prev_date}")
        return history[latest_prev_date].get("portfolio", [])
    return []


def run_tracker(
    username: str = "miulatw",
    use_mock: bool = False,
    headless: bool = True,
    dry_run: bool = False,
    no_notify: bool = False,
    force_notify: bool = False,
    pages_url: str = None
):
    logger.info(f"========== 開始執行 eToro 追蹤任務: @{username} ==========")
    now_taipei = get_taipei_now()
    today_date = now_taipei.strftime("%Y-%m-%d")
    now_time_str = now_taipei.strftime("%Y-%m-%d %H:%M:%S")

    data_dir = os.path.join(BASE_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)
    history_file = os.path.join(data_dir, "history.json")
    latest_file = os.path.join(data_dir, "latest.json")

    # 1. 抓取當前持股資料與餘額
    if use_mock:
        logger.info("採用 Mock 模擬模式...")
        today_portfolio = get_mock_portfolio_data()
        cash_balance = {"available_cash_pct": 18.46, "total_invested_pct": 81.54}
    else:
        scraper = EToroScraper(username=username, headless=headless)
        today_portfolio = scraper.scrape(mock_on_fail=True)
        cash_balance = scraper.cash_balance

    if not today_portfolio:
        logger.error("無法取得任何持股資料，程序終止！")
        return False

    logger.info(f"成功取得今日持股: 共 {len(today_portfolio)} 檔標的。")

    # 2. 載入歷史資料並找出昨日部位與現金進行比對
    history = load_history_data(history_file)
    sorted_prev_dates = sorted([d for d in history.keys() if d < today_date], reverse=True)
    yesterday_date_raw = sorted_prev_dates[0] if sorted_prev_dates else None
    yesterday_portfolio = history[yesterday_date_raw].get("portfolio", []) if yesterday_date_raw else []
    yesterday_cash = history[yesterday_date_raw].get("cash_balance") if yesterday_date_raw else None

    if not yesterday_portfolio and os.path.exists(latest_file):
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                prev_latest = json.load(f)
                if prev_latest.get("date") != today_date:
                    yesterday_portfolio = prev_latest.get("portfolio", [])
                    yesterday_date_raw = prev_latest.get("date")
                    if not yesterday_cash:
                        yesterday_cash = prev_latest.get("cash_balance")
        except Exception:
            pass

    # 計算現金餘額相較昨日之變動量 (Δ%)
    today_avail = float(cash_balance.get("available_cash_pct", 18.46))
    today_invested = float(cash_balance.get("total_invested_pct", 81.54))

    if yesterday_cash:
        yesterday_avail = float(yesterday_cash.get("available_cash_pct", today_avail))
        yesterday_invested = float(yesterday_cash.get("total_invested_pct", today_invested))
        diff_avail = round(today_avail - yesterday_avail, 2)
        diff_invested = round(today_invested - yesterday_invested, 2)
        has_yesterday_cash = True
    else:
        yesterday_avail = today_avail
        yesterday_invested = today_invested
        diff_avail = 0.0
        diff_invested = 0.0
        has_yesterday_cash = False

    enhanced_cash_balance = {
        "available_cash_pct": today_avail,
        "total_invested_pct": today_invested,
        "yesterday_available_cash_pct": yesterday_avail,
        "yesterday_total_invested_pct": yesterday_invested,
        "diff": diff_avail,
        "invested_diff": diff_invested,
        "has_yesterday": has_yesterday_cash
    }

    # 格式化日期為 YYYY/M/D 或 YYYY/MM/DD
    today_date_fmt = now_taipei.strftime("%Y/%m/%d")
    yesterday_date_fmt = datetime.strptime(yesterday_date_raw, "%Y-%m-%d").strftime("%Y/%m/%d") if yesterday_date_raw else None

    # 3. 執行調倉變動比對 (零門檻精確比對)
    analysis_result = PortfolioAnalyzer.analyze(today_portfolio, yesterday_portfolio, threshold=0.0)
    analysis_result["today_date"] = today_date_fmt
    analysis_result["yesterday_date"] = yesterday_date_fmt
    logger.info(f"比對完成: (基準日 {yesterday_date_fmt} vs 今日 {today_date_fmt}) 新開倉 {analysis_result['stats']['new_count']} 檔, 平倉 {analysis_result['stats']['closed_count']} 檔, 加碼 {analysis_result['stats']['increased_count']} 檔, 減碼 {analysis_result['stats']['decreased_count']} 檔 | 可用現金變動: {diff_avail}%")

    # 4. AI 智能摘要生成
    logger.info("生成 Gemini 1.5 Flash 繁體中文調倉總結...")
    ai_summary_text = generate_ai_summary(analysis_result, username=username)
    logger.info(f"AI 摘要:\n{ai_summary_text}")

    # 檢查今日是否已發送過通知 (防重複通知機制)
    already_notified_today = False
    if today_date in history and history[today_date].get("notified", False):
        already_notified_today = True
    elif os.path.exists(latest_file):
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                cur_latest = json.load(f)
                if cur_latest.get("date") == today_date and cur_latest.get("notified", False):
                    already_notified_today = True
        except Exception:
            pass

    # 5. 更新 latest.json 與 history.json
    notified_flag = True if (already_notified_today or not no_notify) else False

    latest_payload = {
        "username": username,
        "date": today_date,
        "update_time": now_time_str,
        "cash_balance": enhanced_cash_balance,
        "portfolio": today_portfolio,
        "ai_summary": ai_summary_text,
        "analysis": analysis_result,
        "notified": notified_flag
    }

    if not dry_run:
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(latest_payload, f, ensure_ascii=False, indent=2)
        logger.info(f"已更新最新數據檔案: {latest_file}")

        # 更新歷史
        history[today_date] = {
            "update_time": now_time_str,
            "cash_balance": enhanced_cash_balance,
            "portfolio": today_portfolio,
            "stats": analysis_result["stats"],
            "ai_summary": ai_summary_text,
            "notified": notified_flag
        }
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        logger.info(f"已更新歷史快照檔案: {history_file}")

        # 6. 生成靜態 index.html 頁面
        logger.info("渲染產生 GitHub Pages 儀表板 (index.html)...")
        builder = PageBuilder()
        builder.render(
            analysis_result=analysis_result,
            ai_summary=ai_summary_text,
            username=username,
            update_time=now_time_str,
            cash_balance=enhanced_cash_balance
        )
    else:
        logger.info("[Dry Run] 跳過寫入 JSON 與 index.html 檔案")

    # 7. 發送推播通知 (具備防重複檢查)
    if no_notify or dry_run:
        logger.info("已指定 --no-notify 或 dry-run，跳過推播發送。")
    elif already_notified_today and not force_notify:
        logger.info(f"⚡ 今日 ({today_date}) 已於稍早成功發送過通知，本次排程自動跳過重複發送 Email/推播 (若需強制發送請帶入 --force-notify)。")
    else:
        logger.info("正在執行推播分發...")
        dispatcher = NotificationDispatcher(username=username, pages_url=pages_url)
        dispatcher.dispatch(analysis_result, ai_summary_text, cash_balance=enhanced_cash_balance)

    logger.info("========== eToro 追蹤任務圓滿完成 ==========")
    return True


def main():
    parser = argparse.ArgumentParser(description="eToro Portfolio Daily Tracker")
    parser.add_argument("--username", default=os.getenv("TARGET_USERNAME", "miulatw"), help="eToro 追蹤用戶名")
    parser.add_argument("--mock", action="store_true", help="使用 Mock 測試數據")
    parser.add_argument("--no-headless", action="store_true", help="顯示瀏覽器視窗")
    parser.add_argument("--dry-run", action="store_true", help="試運行不儲存歷史資料")
    parser.add_argument("--no-notify", action="store_true", help="跳過發送推播通知")
    parser.add_argument("--force-notify", action="store_true", help="強制重新發送推播通知 (忽略今日已通知標記)")
    parser.add_argument("--pages-url", default=os.getenv("PAGES_URL"), help="GitHub Pages 網址")

    args = parser.parse_args()

    run_tracker(
        username=args.username,
        use_mock=args.mock,
        headless=not args.no_headless,
        dry_run=args.dry_run,
        no_notify=args.no_notify,
        force_notify=args.force_notify,
        pages_url=args.pages_url
    )


if __name__ == "__main__":
    main()
