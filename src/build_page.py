"""
HTML 靜態網頁生成器 (Page Builder)
讀取最新調倉分析數據與 AI 摘要，透過 Jinja2 模板渲染輸出為現代深色科技感之儀表板 (支援多投資人切換)。
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
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

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from src.config import INVESTORS, get_investor

logger = logging.getLogger(__name__)


class PageBuilder:
    def __init__(self, template_dir: Optional[str] = None, output_path: Optional[str] = None):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.template_dir = template_dir or os.path.join(self.base_dir, "templates")
        self.output_path = output_path or os.path.join(self.base_dir, "index.html")
        
        self.env = Environment(loader=FileSystemLoader(self.template_dir), autoescape=True)

    def render(
        self,
        analysis_result: Dict[str, Any],
        ai_summary: str,
        username: str = "miulatw",
        update_time: Optional[str] = None,
        cash_balance: Optional[Dict[str, Any]] = None,
        latest_comment: Optional[Dict[str, Any]] = None,
        display_name: Optional[str] = None,
        investors: Optional[List[Dict[str, Any]]] = None,
        output_path: Optional[str] = None
    ) -> str:
        """
        渲染靜態儀表板 HTML 網頁
        """
        template = self.env.get_template("index.html.jinja2")
        formatted_time = update_time or get_taipei_now().strftime("%Y-%m-%d %H:%M:%S")

        portfolio = analysis_result.get("today_portfolio", [])
        changes = analysis_result.get("changes", [])
        # 兼容性補全：確保舊版 changes 數據能順利渲染新版欄位
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

        inv_info = get_investor(username)
        current_display = display_name or inv_info.get("display_name", username)
        inv_list = investors if investors is not None else INVESTORS

        comment = latest_comment or {
            "id": "default",
            "author_name": current_display,
            "username": username,
            "avatar_url": inv_info.get("avatar_url") or "https://etoro-cdn.etorostatic.com/avatars/50X50/8220524/1.jpg",
            "country": "全球",
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
            display_name=current_display,
            investors=inv_list,
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

        target_file = output_path or self.output_path
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"成功生成靜態儀表板網頁 -> {target_file}")
        return target_file


def build_from_latest_json(username: Optional[str] = None) -> List[str]:
    """
    從 data/<username>/latest.json 重新生成對應的 HTML 檔案
    若未指定 username，則重新生成 INVESTORS 清單中所有投資者的網頁
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    targets = [get_investor(username)] if username else INVESTORS
    generated_files = []

    for inv in targets:
        u = inv["username"]
        target_html = os.path.join(base_dir, inv["html_file"])

        # 優先讀取 data/<username>/latest.json，向後相容 data/latest.json
        user_latest = os.path.join(base_dir, "data", u, "latest.json")
        legacy_latest = os.path.join(base_dir, "data", "latest.json")

        latest_file = user_latest if os.path.exists(user_latest) else (legacy_latest if u == "miulatw" and os.path.exists(legacy_latest) else None)

        if not latest_file or not os.path.exists(latest_file):
            logger.warning(f"找不到用戶 [{u}] 之最新數據檔案，跳過生成。")
            continue

        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        builder = PageBuilder(output_path=target_html)
        out = builder.render(
            analysis_result=data["analysis"],
            ai_summary=data.get("ai_summary", "無 AI 摘要"),
            username=data.get("username", u),
            display_name=inv.get("display_name"),
            update_time=data.get("update_time"),
            cash_balance=data.get("cash_balance"),
            latest_comment=data.get("latest_comment"),
            investors=INVESTORS,
            output_path=target_html
        )
        generated_files.append(out)

    return generated_files


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        out_files = build_from_latest_json()
        print(f"網頁生成成功: {out_files}")
    except Exception as e:
        print(f"網頁生成失敗: {e}")
