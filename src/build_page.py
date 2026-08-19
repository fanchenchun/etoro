"""
HTML 靜態網頁生成器 (Page Builder)
讀取最新調倉分析數據與 AI 摘要，透過 Jinja2 模板渲染輸出為現代深色科技感之 index.html。
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader

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

    def render(self, analysis_result: Dict[str, Any], ai_summary: str, username: str = "miulatw", update_time: Optional[str] = None) -> str:
        """
        渲染 index.html
        """
        template = self.env.get_template("index.html.jinja2")
        formatted_time = update_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        portfolio = analysis_result.get("today_portfolio", [])
        changes = analysis_result.get("changes", [])
        stats = analysis_result.get("stats", {})

        html_content = template.render(
            username=username,
            update_time=formatted_time,
            ai_summary=ai_summary,
            stats=stats,
            changes=changes,
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
        update_time=data.get("update_time")
    )


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    try:
        out = build_from_latest_json()
        print(f"網頁生成成功: {out}")
    except Exception as e:
        print(f"網頁生成失敗: {e}")
