"""
HTML 靜態網頁生成器 (Page Builder)
讀取最新調倉分析數據與 AI 摘要，透過 Jinja2 模板渲染輸出為現代深色科技感之 index.html。
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader

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

logger = logging.getLogger(__name__)


class PageBuilder:
    def __init__(self, template_dir: Optional[str] = None, output_path: Optional[str] = None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.template_dir = template_dir or os.path.join(base_dir, "templates")
        self.output_path = output_path or os.path.join(base_dir, "index.html")
        
        self.env = Environment(loader=FileSystemLoader(self.template_dir), autoescape=True)

    def render(
        self,
        analysis_result: Dict[str, Any],
        ai_summary: str,
        username: str = "miulatw",
        update_time: Optional[str] = None,
        cash_balance: Optional[Dict[str, Any]] = None,
        latest_comment: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        渲染 index.html
        """
        template = self.env.get_template("index.html.jinja2")
        formatted_time = update_time or get_taipei_now().strftime("%Y-%m-%d %H:%M:%S")

        portfolio = analysis_result.get("today_portfolio", [])
        changes = analysis_result.get("changes", [])
        # 兼容性補全：確保舊版 changes 數據能順利渲染新版 12 欄位
        for c in changes:
            if "today_invest_alloc" not in c:
                c["yesterday_invest_alloc"] = c.get("yesterday_alloc", 0.0)
                c["today_invest_alloc"] = c.get("today_alloc", 0.0)
                c["invest_diff"] = c.get("diff", 0.0)
                c["invest_status"] = c.get("status", "UNCHANGED")
                c["invest_status_badge"] = c.get("status_badge", "")
                c["invest_status_color"] = c.get("status_color", "")
            if "today_value_alloc" not in c:
                c["today_value_alloc"] = c.get("today_alloc", 0.0)
                c["yesterday_value_alloc"] = c.get("yesterday_value_alloc")
                c["value_diff"] = c.get("value_diff")
                c["value_status"] = c.get("value_status", "INITIAL")
                c["value_status_badge"] = c.get("value_status_badge", "📌 基準持倉")
                c["value_status_color"] = c.get("value_status_color", "text-slate-300 bg-slate-800/60 border-slate-600/30")

        stats = analysis_result.get("stats", {})
        cash = cash_balance or {
            "available_cash_pct": 18.46,
            "total_invested_pct": 81.54,
            "yesterday_available_cash_pct": 18.46,
            "yesterday_total_invested_pct": 81.54,
            "diff": 0.0,
            "invested_diff": 0.0,
            "has_yesterday": False
        }
        today_date = analysis_result.get("today_date") or get_taipei_now().strftime("%Y/%m/%d")
        yesterday_date = analysis_result.get("yesterday_date")

        comment = latest_comment or {
            "id": "default",
            "author_name": "Yueh Nung Hung",
            "username": username,
            "avatar_url": "https://etoro-cdn.etorostatic.com/avatars/50X50/8220524/1.jpg",
            "country": "臺灣",
            "created_at_formatted": "",
            "relative_time": "近期",
            "content": "暫無最新動態留言",
            "likes_count": 0,
            "comments_count": 0,
            "shares_count": 0,
            "post_url": f"https://www.etoro.com/zh-tw/people/{username}",
            "is_new": False
        }

        html_content = template.render(
            username=username,
            update_time=formatted_time,
            today_date=today_date,
            yesterday_date=yesterday_date,
            ai_summary=ai_summary,
            stats=stats,
            changes=changes,
            cash_balance=cash,
            latest_comment=comment,
            portfolio_json=json.dumps(portfolio, ensure_ascii=False),
            changes_json=json.dumps(changes, ensure_ascii=False)
        )

        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"成功生成靜態儀表板網頁 -> {self.output_path}")
        return self.output_path


def build_from_latest_json() -> str:
    """
    從 data/latest.json 重新生成 index.html
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    latest_file = os.path.join(base_dir, "data", "latest.json")

    if not os.path.exists(latest_file):
        raise FileNotFoundError(f"找不到最新數據檔案: {latest_file}")

    with open(latest_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    builder = PageBuilder()
    return builder.render(
        analysis_result=data["analysis"],
        ai_summary=data.get("ai_summary", "無 AI 摘要"),
        username=data.get("username", "miulatw"),
        update_time=data.get("update_time"),
        cash_balance=data.get("cash_balance"),
        latest_comment=data.get("latest_comment")
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        out = build_from_latest_json()
        print(f"網頁生成成功: {out}")
    except Exception as e:
        print(f"網頁生成失敗: {e}")
