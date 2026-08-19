"""
多管道通知推播模組 (Notifier)
支援:
1. LINE Notify (LINE_NOTIFY_TOKEN)
2. Telegram Bot (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
3. Email SMTP (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, NOTIFICATION_EMAIL)
4. Discord Webhook (DISCORD_WEBHOOK_URL)
"""

import os
import sys
import smtplib
import logging
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional
from datetime import datetime

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    def __init__(self, username: str = "miulatw", pages_url: Optional[str] = None):
        self.username = username
        self.pages_url = pages_url or os.getenv("PAGES_URL", "https://github.com")

    def build_message_text(self, analysis_result: Dict[str, Any], ai_summary: str) -> str:
        """
        組合純文字通知內容
        """
        stats = analysis_result["stats"]
        changes = analysis_result["changes"]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        lines = [
            f"🚀 【eToro 投資組合追蹤 - {self.username}】",
            f"📅 更新時間：{now_str}",
            "",
            "🤖 【AI 智能調倉總結】",
            ai_summary,
            "",
            "📊 【部位變動明細】"
        ]

        if not stats["has_significant_changes"]:
            lines.append("• 今日部位無顯著變動，維持原有持股配置。")
        else:
            if stats["new_symbols"]:
                new_items = [f"{c['symbol']} ({c['today_alloc']}%)" for c in changes if c["status"] == "NEW"]
                lines.append(f"🆕 新開倉: {', '.join(new_items)}")

            if stats["closed_symbols"]:
                closed_items = [f"{c['symbol']} (原 {c['yesterday_alloc']}%)" for c in changes if c["status"] == "CLOSED"]
                lines.append(f"❌ 已清倉: {', '.join(closed_items)}")

            increased = [f"{c['symbol']} (+{c['diff']}%)" for c in changes if c["status"] == "INCREASED"]
            if increased:
                lines.append(f"🟢 加碼: {', '.join(increased)}")

            decreased = [f"{c['symbol']} ({c['diff']}%)" for c in changes if c["status"] == "DECREASED"]
            if decreased:
                lines.append(f"🔴 減碼: {', '.join(decreased)}")

        lines.append("")
        lines.append(f"🔗 完整視覺化儀表板：{self.pages_url}")
        return "\n".join(lines)

    def build_html_report(self, analysis_result: Dict[str, Any], ai_summary: str) -> str:
        """
        生成適合 Email 的 HTML 格式內容
        """
        text_content = self.build_message_text(analysis_result, ai_summary)
        # 簡單將換行替換為 <br> 並用深色區塊封裝
        formatted_summary = ai_summary.replace("\n", "<br>")
        
        rows_html = ""
        for c in analysis_result["changes"][:10]:
            diff_color = "#10b981" if c["diff"] > 0 else ("#f43f5e" if c["diff"] < 0 else "#94a3b8")
            badge = c["status_badge"]
            rows_html += f"""
            <tr style="border-bottom: 1px solid #334155;">
                <td style="padding: 10px; font-weight: bold; color: #f8fafc;">{c['symbol']}</td>
                <td style="padding: 10px; color: #cbd5e1;">{c['name']}</td>
                <td style="padding: 10px; color: #94a3b8;">{c['yesterday_alloc']}%</td>
                <td style="padding: 10px; color: #f8fafc; font-weight: bold;">{c['today_alloc']}%</td>
                <td style="padding: 10px; color: {diff_color}; font-weight: bold;">{'+' if c['diff'] > 0 else ''}{c['diff']}%</td>
                <td style="padding: 10px;">{badge}</td>
            </tr>
            """

        html = f"""
        <div style="background-color: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 24px; border-radius: 12px; max-width: 650px; margin: auto;">
            <h2 style="color: #38bdf8; margin-top: 0;">🚀 eToro 投資組合追蹤 - {self.username}</h2>
            <div style="background-color: #1e293b; padding: 16px; border-radius: 8px; border-left: 4px solid #38bdf8; margin-bottom: 20px;">
                <h4 style="margin: 0 0 8px 0; color: #7dd3fc;">🤖 AI 智能調倉總結</h4>
                <p style="margin: 0; line-height: 1.6; color: #f1f5f9;">{formatted_summary}</p>
            </div>
            <h3 style="color: #cbd5e1; margin-bottom: 12px;">📊 重點部位變動表</h3>
            <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 14px;">
                <thead>
                    <tr style="background-color: #1e293b; color: #94a3b8;">
                        <th style="padding: 10px;">代號</th>
                        <th style="padding: 10px;">名稱</th>
                        <th style="padding: 10px;">昨日</th>
                        <th style="padding: 10px;">今日</th>
                        <th style="padding: 10px;">變動</th>
                        <th style="padding: 10px;">狀態</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
            <div style="margin-top: 24px; text-align: center;">
                <a href="{self.pages_url}" style="background-color: #0284c7; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">查看完整 GitHub Pages 儀表板</a>
            </div>
        </div>
        """
        return html

    def send_line_notify(self, message: str) -> bool:
        token = os.getenv("LINE_NOTIFY_TOKEN")
        if not token:
            return False
        try:
            url = "https://notify-api.line.me/api/notify"
            headers = {"Authorization": f"Bearer {token}"}
            payload = {"message": f"\n{message}"}
            res = requests.post(url, headers=headers, data=payload, timeout=10)
            if res.status_code == 200:
                logger.info("LINE Notify 推播發送成功！")
                return True
            logger.warning(f"LINE Notify 推播失敗: {res.status_code} - {res.text}")
        except Exception as e:
            logger.error(f"LINE Notify 例外: {e}")
        return False

    def send_telegram(self, message: str) -> bool:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            return False
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "disable_web_page_preview": False
            }
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code == 200:
                logger.info("Telegram Bot 推播發送成功！")
                return True
            logger.warning(f"Telegram Bot 推播失敗: {res.status_code} - {res.text}")
        except Exception as e:
            logger.error(f"Telegram Bot 例外: {e}")
        return False

    def send_email(self, subject: str, text_body: str, html_body: str) -> bool:
        host = os.getenv("SMTP_HOST")
        port = int(os.getenv("SMTP_PORT", 587))
        user = os.getenv("SMTP_USER")
        password = os.getenv("SMTP_PASS")
        recipient = os.getenv("NOTIFICATION_EMAIL")

        if not all([host, user, password, recipient]):
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = user
            msg["To"] = recipient

            part1 = MIMEText(text_body, "plain", "utf-8")
            part2 = MIMEText(html_body, "html", "utf-8")
            msg.attach(part1)
            msg.attach(part2)

            with smtplib.SMTP(host, port, timeout=15) as server:
                server.starttls()
                server.login(user, password)
                server.sendmail(user, [recipient], msg.as_string())

            logger.info(f"Email 通知發送成功 -> {recipient}")
            return True
        except Exception as e:
            logger.error(f"Email SMTP 發送失敗: {e}")
            return False

    def send_discord(self, message: str) -> bool:
        webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        if not webhook_url:
            return False
        try:
            payload = {"content": message}
            res = requests.post(webhook_url, json=payload, timeout=10)
            if res.status_code in [200, 204]:
                logger.info("Discord Webhook 發送成功！")
                return True
            logger.warning(f"Discord 發送失敗: {res.status_code}")
        except Exception as e:
            logger.error(f"Discord 例外: {e}")
        return False

    def dispatch(self, analysis_result: Dict[str, Any], ai_summary: str) -> Dict[str, bool]:
        """
        統一分發推播通知至所有已配置之管道
        """
        text_msg = self.build_message_text(analysis_result, ai_summary)
        html_msg = self.build_html_report(analysis_result, ai_summary)
        subject = f"📊 eToro 調倉日報 ({self.username}) - {datetime.now().strftime('%m/%d')}"

        results = {
            "telegram": self.send_telegram(text_msg),
            "line": self.send_line_notify(text_msg),
            "email": self.send_email(subject, text_msg, html_msg),
            "discord": self.send_discord(text_msg)
        }

        sent_channels = [k for k, v in results.items() if v]
        if sent_channels:
            logger.info(f"已成功推送至管道: {', '.join(sent_channels)}")
        else:
            logger.info("未偵測到有效通知 Token/密碼或所有推播管道未開啟。")

        return results


if __name__ == "__main__":
    dispatcher = NotificationDispatcher("miulatw")
    sample_analysis = {
        "stats": {
            "total_today": 14,
            "has_significant_changes": True,
            "new_symbols": ["ARM"],
            "closed_symbols": ["COIN"],
        },
        "changes": [
            {"symbol": "ARM", "name": "Arm Holdings", "yesterday_alloc": 0.0, "today_alloc": 2.8, "diff": 2.8, "status": "NEW", "status_badge": "🆕 新開倉"},
            {"symbol": "NVDA", "name": "NVIDIA", "yesterday_alloc": 14.0, "today_alloc": 16.5, "diff": 2.5, "status": "INCREASED", "status_badge": "🟢 加碼"},
            {"symbol": "COIN", "name": "Coinbase", "yesterday_alloc": 2.2, "today_alloc": 0.0, "diff": -2.2, "status": "CLOSED", "status_badge": "❌ 已平倉"},
        ]
    }
    sample_ai = "【今日調倉焦點】miulatw 今日新開倉 ARM (2.8%) 並持續加碼龍頭 NVDA (+2.5%)，同時全數平倉加密貨幣相關之 COIN。【策略觀點】資金顯著回流 AI 運算核心與半導體供應鏈，降低高波動板塊佔比。"
    print(dispatcher.build_message_text(sample_analysis, sample_ai))
