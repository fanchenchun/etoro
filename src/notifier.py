"""
多管道通知推播模組 (Notifier)
支援:
1. LINE Messaging API Bot (LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID)
2. Telegram Bot (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
3. Email SMTP (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, NOTIFICATION_EMAIL)
4. Discord Webhook (DISCORD_WEBHOOK_URL)
5. LINE Notify (舊版相容)
"""

import os
import sys
import smtplib
import logging
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta

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


class NotificationDispatcher:
    def __init__(self, username: str = "miulatw", pages_url: Optional[str] = None):
        self.username = username
        self.pages_url = pages_url or os.getenv("PAGES_URL", "https://fanchenchun.github.io/etoro/")

    def build_message_text(self, analysis_result: Dict[str, Any], ai_summary: str, cash_balance: Optional[Dict[str, Any]] = None) -> str:
        """
        組合純文字通知內容 (針對 LINE Bot / Telegram 等管道)
        """
        stats = analysis_result.get("stats", {})
        changes = analysis_result.get("changes", [])
        now_str = get_taipei_now().strftime("%Y-%m-%d %H:%M")
        cash = cash_balance or {"available_cash_pct": 18.46, "total_invested_pct": 81.54}

        lines = [
            f"🚀 【eToro 每日調倉日報 - @{self.username}】",
            f"📅 更新時間：{now_str}",
            "",
            "🤖 【AI 每日調倉洞察總結】",
            f"{ai_summary}",
            "",
            "📊 【重點部位變動摘要】"
        ]

        if stats.get("is_first_day"):
            top5 = [f"{c['symbol']}({c['today_alloc']}%)" for c in changes[:5]]
            lines.append(f"📌 首日建立基準持倉：共 {stats.get('total_today', 37)} 檔標的")
            lines.append(f"👑 前五大配置：{', '.join(top5)}")
        elif not stats.get("has_significant_changes"):
            lines.append("⚪ 今日持倉無重大調整，各標的維持原有配置。")
        else:
            if stats.get("new_symbols"):
                new_items = [f"{c['symbol']} ({c['today_alloc']}%)" for c in changes if c["status"] == "NEW"]
                lines.append(f"🆕 新開倉: {', '.join(new_items)}")

            if stats.get("closed_symbols"):
                closed_items = [f"{c['symbol']} (原 {c['yesterday_alloc']}%)" for c in changes if c["status"] == "CLOSED"]
                lines.append(f"❌ 已清倉: {', '.join(closed_items)}")

            increased = [f"{c['symbol']} (+{c['diff']}%)" for c in changes if c["status"] == "INCREASED"]
            if increased:
                lines.append(f"🟢 加碼: {', '.join(increased[:5])}")

            decreased = [f"{c['symbol']} ({c['diff']}%)" for c in changes if c["status"] == "DECREASED"]
            if decreased:
                lines.append(f"🔴 減碼: {', '.join(decreased[:5])}")

        cash_diff = cash.get("diff", 0.0)
        if stats.get("is_first_day") or not cash.get("has_yesterday", True):
            cash_diff_label = "基準日"
        elif cash_diff > 0:
            cash_diff_label = f"+{cash_diff}% vs昨日"
        elif cash_diff < 0:
            cash_diff_label = f"{cash_diff}% vs昨日"
        else:
            cash_diff_label = "持平 0.0% vs昨日"

        lines.append(f"💰 帳戶未投資現金: {cash.get('available_cash_pct', 18.46)}% ({cash_diff_label}) | 已投資: {cash.get('total_invested_pct', 81.54)}%")
        lines.append("")
        lines.append(f"🔗 完整視覺化儀表板：{self.pages_url}")
        return "\n".join(lines)

    def build_html_report(self, analysis_result: Dict[str, Any], ai_summary: str, cash_balance: Optional[Dict[str, Any]] = None) -> str:
        """
        生成適合 Email 的深色科技感 HTML 格式報表
        """
        formatted_summary = ai_summary.replace("\n", "<br>")
        cash = cash_balance or {"available_cash_pct": 18.46, "total_invested_pct": 81.54, "diff": 0.0}
        now_str = get_taipei_now().strftime("%Y-%m-%d %H:%M")
        
        cash_diff = cash.get("diff", 0.0)
        if analysis_result.get("stats", {}).get("is_first_day") or not cash.get("has_yesterday", True):
            cash_diff_str = "基準日"
            cash_diff_color = "#94a3b8"
        elif cash_diff > 0:
            cash_diff_str = f"+{cash_diff}% vs昨日"
            cash_diff_color = "#10b981"
        elif cash_diff < 0:
            cash_diff_str = f"{cash_diff}% vs昨日"
            cash_diff_color = "#f43f5e"
        else:
            cash_diff_str = "持平 0.0% vs昨日"
            cash_diff_color = "#94a3b8"

        rows_html = ""
        for c in analysis_result.get("changes", [])[:12]:
            diff_color = "#10b981" if c.get("diff", 0) > 0 else ("#f43f5e" if c.get("diff", 0) < 0 else "#94a3b8")
            badge = c.get("status_badge", "⚪ 持平")
            diff_str = f"+{c['diff']}%" if c.get('diff', 0) > 0 else (f"{c['diff']}%" if c.get('diff', 0) < 0 else "0.0%")
            
            rows_html += f"""
            <tr style="border-bottom: 1px solid #1e293b;">
                <td style="padding: 10px 8px; font-weight: bold; color: #f8fafc;">{c['symbol']}</td>
                <td style="padding: 10px 8px; color: #cbd5e1;">{c['name']}</td>
                <td style="padding: 10px 8px; text-align: right; color: #94a3b8;">{c['yesterday_alloc']}%</td>
                <td style="padding: 10px 8px; text-align: right; color: #f8fafc; font-weight: bold;">{c['today_alloc']}%</td>
                <td style="padding: 10px 8px; text-align: right; color: {diff_color}; font-weight: bold;">{diff_str}</td>
                <td style="padding: 10px 8px; text-align: center;">{badge}</td>
            </tr>
            """

        html = f"""
        <div style="background-color: #090d16; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 24px; border-radius: 12px; max-width: 650px; margin: auto; border: 1px solid #1f2937;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1f2937; padding-bottom: 12px; margin-bottom: 16px;">
                <h2 style="color: #38bdf8; margin: 0; font-size: 20px;">🚀 eToro 調倉日報 - @{self.username}</h2>
                <span style="color: #94a3b8; font-size: 12px;">{now_str}</span>
            </div>

            <!-- AI Summary Hero Card -->
            <div style="background-color: #111827; padding: 18px; border-radius: 10px; border-left: 4px solid #10b981; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                <h3 style="margin: 0 0 10px 0; color: #34d399; font-size: 15px; display: flex; align-items: center;">
                    🤖 AI 每日調倉洞察總結
                </h3>
                <p style="margin: 0; line-height: 1.7; color: #f1f5f9; font-size: 14px;">{formatted_summary}</p>
            </div>

            <!-- Cash KPI -->
            <div style="background-color: #111827; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: #cbd5e1; border: 1px solid #1e293b;">
                <div>
                    💰 <strong>未投資現金：</strong><span style="color: #818cf8; font-weight: bold; font-size: 14px;">{cash.get('available_cash_pct', 18.46)}%</span>
                    <span style="color: {cash_diff_color}; font-size: 12px; margin-left: 6px; font-weight: 500;">({cash_diff_str})</span>
                </div>
                <div>
                    📈 <strong>已投資比例：</strong><span style="color: #f1f5f9; font-weight: bold;">{cash.get('total_invested_pct', 81.54)}%</span>
                </div>
            </div>

            <!-- Table -->
            <h3 style="color: #cbd5e1; font-size: 15px; margin-bottom: 10px;">📊 重點持股變動對照表</h3>
            <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 13px;">
                <thead>
                    <tr style="background-color: #111827; color: #94a3b8; border-bottom: 1px solid #334155;">
                        <th style="padding: 8px;">代號</th>
                        <th style="padding: 8px;">名稱</th>
                        <th style="padding: 8px; text-align: right;">昨日 ({analysis_result.get('yesterday_date', '基準')})</th>
                        <th style="padding: 8px; text-align: right;">今日 ({analysis_result.get('today_date', '今日')})</th>
                        <th style="padding: 8px; text-align: right;">變動</th>
                        <th style="padding: 8px; text-align: center;">狀態</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>

            <div style="margin-top: 24px; text-align: center;">
                <a href="{self.pages_url}" style="background-color: #10b981; color: #04100c; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block; font-size: 14px;">查看完整視覺化儀表板</a>
            </div>
            <div style="margin-top: 16px; text-align: center; color: #64748b; font-size: 11px;">
                此郵件由 GitHub Actions 每日自動排程發送 | 僅供數據追蹤參考
            </div>
        </div>
        """
        return html

    def send_line_bot_message(self, message: str) -> bool:
        channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
        user_id = os.getenv("LINE_USER_ID", "").strip()
        
        if not channel_access_token or not user_id:
            return False

        try:
            url = "https://api.line.me/v2/bot/message/push"
            headers = {
                "Authorization": f"Bearer {channel_access_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "to": user_id,
                "messages": [
                    {
                        "type": "text",
                        "text": message
                    }
                ]
            }
            res = requests.post(url, headers=headers, json=payload, timeout=12)
            if res.status_code == 200:
                logger.info("LINE Messaging API 官方 Bot 訊息推送成功！")
                return True
            logger.warning(f"LINE Messaging API 推送失敗: {res.status_code} - {res.text}")
        except Exception as e:
            logger.error(f"LINE Messaging API 例外: {e}")
        return False

    def send_line_notify(self, message: str) -> bool:
        token = os.getenv("LINE_NOTIFY_TOKEN", "").strip()
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
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
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
        host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
        port_str = os.getenv("SMTP_PORT", "587").strip()
        port = int(port_str) if port_str.isdigit() else 587
        user = os.getenv("SMTP_USER", "").strip()
        # 自動清理密碼中的空格與換行 (避免從 Google 複製出來時帶有空格)
        password = os.getenv("SMTP_PASS", "").strip().replace(" ", "").replace("\r", "").replace("\n", "")
        recipient_raw = (os.getenv("NOTIFICATION_EMAIL") or user).strip()

        if not user or not password or not recipient_raw:
            logger.info("Email 設定未完整 (缺少 SMTP_USER, SMTP_PASS 或 NOTIFICATION_EMAIL)，跳過發送。")
            return False

        # 支援逗號或分號分隔的多個收件人
        import re
        recipients = [r.strip() for r in re.split(r"[,;]+", recipient_raw) if r.strip()]
        if not recipients:
            logger.warning("未解析出有效的收件人 Email 地址")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"eToro Tracker <{user}>"
            msg["To"] = ", ".join(recipients)

            part1 = MIMEText(text_body, "plain", "utf-8")
            part2 = MIMEText(html_body, "html", "utf-8")
            msg.attach(part1)
            msg.attach(part2)

            if port == 465:
                # SSL 連線 (Port 465)
                with smtplib.SMTP_SSL(host, port, timeout=20) as server:
                    server.login(user, password)
                    server.sendmail(user, recipients, msg.as_string())
            else:
                # STARTTLS 連線 (Port 587 或其他)
                with smtplib.SMTP(host, port, timeout=20) as server:
                    server.starttls()
                    server.login(user, password)
                    server.sendmail(user, recipients, msg.as_string())

            logger.info(f"Email 通知發送成功 -> {', '.join(recipients)}")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"Email SMTP 身份驗證失敗 (請確認 Gmail 應用程式密碼正確且無空格): {e}")
            return False
        except Exception as e:
            logger.error(f"Email SMTP 發送失敗: {e}")
            return False

    def send_discord(self, message: str) -> bool:
        webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
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

    def dispatch(self, analysis_result: Dict[str, Any], ai_summary: str, cash_balance: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        """
        統一分發推播通知至所有已配置之管道
        """
        text_msg = self.build_message_text(analysis_result, ai_summary, cash_balance)
        html_msg = self.build_html_report(analysis_result, ai_summary, cash_balance)
        date_str = get_taipei_now().strftime('%m/%d')
        subject = f"📊 【eToro 調倉日報】@{self.username} - {date_str}"

        results = {
            "line_bot": self.send_line_bot_message(text_msg),
            "line_notify": self.send_line_notify(text_msg),
            "telegram": self.send_telegram(text_msg),
            "email": self.send_email(subject, text_msg, html_msg),
            "discord": self.send_discord(text_msg)
        }

        sent_channels = [k for k, v in results.items() if v]
        if sent_channels:
            logger.info(f"已成功推送至管道: {', '.join(sent_channels)}")
        else:
            logger.info("未偵測到有效通知 Token/密碼或所有推播管道未開啟。")

        return results
