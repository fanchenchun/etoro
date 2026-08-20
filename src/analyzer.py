"""
投資組合變動比對分析模組 (Analyzer)
負責比對今日與昨日持股，計算各標的佔比變動 (Δ%)，
精確標註：🆕新開倉 (NEW)、❌全數平倉 (CLOSED)、🟢加碼 (INCREASED)、🔴減碼 (DECREASED)、⚪持平 (UNCHANGED)。
規則：只要 diff > 0 即為加碼，diff < 0 即為減碼，diff == 0 為持平。
"""

import sys
import logging
from typing import Dict, List, Any, Optional

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger(__name__)

STATUS_CONFIG = {
    "NEW": {"label": "新開倉", "badge": "🆕 新開倉", "color": "text-emerald-400 bg-emerald-950/60 border-emerald-500/30", "icon": "🆕"},
    "CLOSED": {"label": "已清倉", "badge": "❌ 已平倉", "color": "text-rose-400 bg-rose-950/60 border-rose-500/30", "icon": "❌"},
    "INCREASED": {"label": "加碼", "badge": "🟢 加碼", "color": "text-green-400 bg-green-950/60 border-green-500/30", "icon": "🟢"},
    "DECREASED": {"label": "減碼", "badge": "🔴 減碼", "color": "text-amber-400 bg-amber-950/60 border-amber-500/30", "icon": "🔴"},
    "UNCHANGED": {"label": "持平", "badge": "⚪ 持平", "color": "text-slate-400 bg-slate-800/60 border-slate-700/30", "icon": "⚪"},
    "INITIAL": {"label": "基準持倉", "badge": "📌 基準持倉", "color": "text-slate-300 bg-slate-800/60 border-slate-600/30", "icon": "📌"},
}


class PortfolioAnalyzer:
    @staticmethod
    def analyze(today_portfolio: List[Dict[str, Any]], yesterday_portfolio: Optional[List[Dict[str, Any]]] = None, threshold: float = 0.0) -> Dict[str, Any]:
        """
        比對今日與昨日持股
        只要 diff > 0 判定為加碼，diff < 0 判定為減碼
        """
        is_first_day = not yesterday_portfolio or len(yesterday_portfolio) == 0

        today_map = {item["symbol"].upper(): item for item in today_portfolio}
        yesterday_map = {item["symbol"].upper(): item for item in (yesterday_portfolio or [])}

        all_symbols = sorted(list(set(today_map.keys()) | set(yesterday_map.keys())))
        
        changes = []
        new_items = []
        closed_items = []
        increased_items = []
        decreased_items = []
        unchanged_items = []

        for sym in all_symbols:
            in_today = sym in today_map
            in_yesterday = sym in yesterday_map

            today_alloc = float(today_map[sym]["allocation"]) if in_today else 0.0
            
            if is_first_day:
                yesterday_alloc = today_alloc
                diff = 0.0
                status = "UNCHANGED"
                unchanged_items.append(sym)
            else:
                yesterday_alloc = float(yesterday_map[sym]["allocation"]) if in_yesterday else 0.0
                diff = round(today_alloc - yesterday_alloc, 2)

                if in_today and not in_yesterday:
                    status = "NEW"
                    new_items.append(sym)
                elif not in_today and in_yesterday:
                    status = "CLOSED"
                    closed_items.append(sym)
                elif diff > 0.0:
                    status = "INCREASED"
                    increased_items.append(sym)
                elif diff < 0.0:
                    status = "DECREASED"
                    decreased_items.append(sym)
                else:
                    status = "UNCHANGED"
                    unchanged_items.append(sym)

            name = today_map[sym]["name"] if in_today else yesterday_map[sym].get("name", sym)
            instrument_type = today_map[sym].get("instrument_type", "Stocks") if in_today else yesterday_map[sym].get("instrument_type", "Stocks")
            cfg = STATUS_CONFIG.get(status, STATUS_CONFIG["UNCHANGED"])

            changes.append({
                "symbol": sym,
                "name": name,
                "instrument_type": instrument_type,
                "yesterday_alloc": yesterday_alloc,
                "today_alloc": today_alloc,
                "diff": diff,
                "status": status,
                "status_label": cfg["label"],
                "status_badge": cfg["badge"],
                "status_color": cfg["color"],
                "status_icon": cfg["icon"],
                "is_active": in_today
            })

        # 排序邏輯：今日持倉依「今日佔比 (today_alloc)」由大到小降冪排序；已平倉標的排在最下方
        def sort_priority(item):
            return (
                0 if item["is_active"] else 1,
                -item["today_alloc"],
                -item["yesterday_alloc"]
            )

        sorted_changes = sorted(changes, key=sort_priority)

        # 統計概覽
        summary_stats = {
            "is_first_day": is_first_day,
            "total_today": len(today_portfolio),
            "total_yesterday": len(yesterday_portfolio) if yesterday_portfolio else len(today_portfolio),
            "new_count": len(new_items),
            "closed_count": len(closed_items),
            "increased_count": len(increased_items),
            "decreased_count": len(decreased_items),
            "unchanged_count": len(unchanged_items),
            "new_symbols": new_items,
            "closed_symbols": closed_items,
            "increased_symbols": increased_items,
            "decreased_symbols": decreased_items,
            "has_significant_changes": (len(new_items) > 0 or len(closed_items) > 0 or len(increased_items) > 0 or len(decreased_items) > 0) and not is_first_day
        }

        return {
            "stats": summary_stats,
            "changes": sorted_changes,
            "today_portfolio": today_portfolio,
            "yesterday_portfolio": yesterday_portfolio or []
        }

    @staticmethod
    def format_text_report(analysis_result: Dict[str, Any], username: str = "miulatw") -> str:
        """
        將分析結果格式化為文字版通知摘要
        """
        stats = analysis_result["stats"]
        changes = analysis_result["changes"]
        
        lines = []
        lines.append(f"📊 eToro 投資組合追蹤 ({username})")

        if stats.get("is_first_day"):
            top3 = [f"{c['symbol']} ({c['today_alloc']}%)" for c in changes[:5]]
            lines.append(f"📌 首日建立基準持倉：共 {stats['total_today']} 檔標的")
            lines.append(f"前五大配置：{', '.join(top3)}")
            lines.append("⚡ 明日起將每日自動比對最新調倉變動。")
            return "\n".join(lines)

        lines.append(f"今日持倉: {stats['total_today']} 檔 | 變動: +{stats['new_count']} 新倉, -{stats['closed_count']} 平倉, 🟢{stats['increased_count']} 加碼, 🔴{stats['decreased_count']} 減碼")
        lines.append("-" * 32)

        if not stats["has_significant_changes"]:
            lines.append("⚡ 今日投資組合維持持平，無顯著調倉動作。")
            return "\n".join(lines)

        if stats["new_symbols"]:
            new_details = [f"{c['symbol']} ({c['today_alloc']}%)" for c in changes if c["status"] == "NEW"]
            lines.append(f"🆕 新開倉: {', '.join(new_details)}")

        if stats["closed_symbols"]:
            closed_details = [f"{c['symbol']} (原 {c['yesterday_alloc']}%)" for c in changes if c["status"] == "CLOSED"]
            lines.append(f"❌ 已清倉: {', '.join(closed_details)}")

        increased = [c for c in changes if c["status"] == "INCREASED"]
        if increased:
            inc_strs = [f"{c['symbol']} (+{c['diff']}%)" for c in increased[:5]]
            lines.append(f"🟢 加碼: {', '.join(inc_strs)}")

        decreased = [c for c in changes if c["status"] == "DECREASED"]
        if decreased:
            dec_strs = [f"{c['symbol']} ({c['diff']}%)" for c in decreased[:5]]
            lines.append(f"🔴 減碼: {', '.join(dec_strs)}")

        return "\n".join(lines)
