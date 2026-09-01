"""
AI 智能摘要模組 (Gemini 1.5 Flash)
利用 Google Gemini 1.5 Flash API 生成 100~150 字結構化繁體中文調倉總結
支援:
1. Google 官方 Gemini REST API (使用 requests，跨平台零 C++ 編譯依賴)
2. google-generativeai SDK (若已安裝則可選用)
3. 自動降級機制 (Fallback Rule-based Summary)，保證在無 Key 或網路異常下仍能輸出優質摘要。
"""

import os
import sys
import json
import logging
import requests
from typing import Dict, Any, Optional

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger(__name__)


def generate_fallback_summary(analysis_result: Dict[str, Any], username: str = "miulatw") -> str:
    """
    當無 API Key 或調用失敗時的規則型結構化摘要
    """
    stats = analysis_result["stats"]
    changes = analysis_result["changes"]

    if stats.get("is_first_day"):
        top5 = [f"{c['symbol']}({c['today_alloc']}%)" for c in changes[:5]]
        return (
            f"【建立持倉基準】{username} 目前投資組合共持有 {stats['total_today']} 檔美股與 ETF 標的。"
            f"前五大核心重倉依序為：{'、'.join(top5)}。"
            f"系統已建立今日歷史基準快照，自下一個交易日起將每日自動追蹤比對調倉增減與新開平倉動作。"
        )

    if not stats["has_significant_changes"]:
        return f"【今日持倉無明顯變動】{username} 今日投資組合維持穩定，各主要美股持倉比重未見顯著增減，整體維持原有之科技與大型權值股長期配置架構。"

    actions = []
    if stats["new_symbols"]:
        new_names = [f"{c['symbol']}({c['today_alloc']}%)" for c in changes if c["status"] == "NEW"]
        actions.append(f"新開倉 {', '.join(new_names)}")

    if stats["closed_symbols"]:
        closed_names = [f"{c['symbol']}" for c in changes if c["status"] == "CLOSED"]
        actions.append(f"全數平倉 {', '.join(closed_names)}")

    increased = [f"{c['symbol']}(+{c['diff']}%)" for c in changes if c["status"] == "INCREASED"]
    if increased:
        actions.append(f"加碼 {', '.join(increased[:3])}")

    decreased = [f"{c['symbol']}({c['diff']}%)" for c in changes if c["status"] == "DECREASED"]
    if decreased:
        actions.append(f"減碼 {', '.join(decreased[:3])}")

    summary_text = (
        f"【調倉動態】{username} 今日主要操作為：{'；'.join(actions)}。"
        f"目前總持股維持 {stats['total_today']} 檔。"
        f"整體策略顯示投資人正針對強勢龍頭進行微調，資金主要在主要成長股與題材股間進行權重優化。"
    )
    return summary_text


def _call_gemini_rest_api(prompt: str, api_key: str) -> Optional[str]:
    """
    直接透過 Google Gemini 官方 REST API 呼叫 Gemini Flash 模型 (具備多版本模型輪替容錯)
    """
    models_to_try = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-pro"]
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 300
        }
    }

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=20)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"].strip()
            else:
                logger.warning(f"Gemini REST API ({model_name}) 回應狀態碼 {res.status_code}: {res.text[:160]}")
        except Exception as e:
            logger.warning(f"Gemini REST API ({model_name}) 請求例外: {e}")

    return None


def generate_ai_summary(analysis_result: Dict[str, Any], username: str = "miulatw", api_key: Optional[str] = None) -> str:
    """
    呼叫 Gemini 1.5 Flash API 產生繁體中文分析摘要
    """
    api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("未偵測到 GEMINI_API_KEY，啟用規則型摘要生成。")
        return generate_fallback_summary(analysis_result, username)

    stats = analysis_result["stats"]
    changes = analysis_result["changes"]

    if stats.get("is_first_day"):
        top5 = [f"{c['symbol']} ({c['today_alloc']}%)" for c in changes[:5]]
        prompt = f"""
你是一位專業的美股投資分析師。這是追蹤 eToro 明星投資者「{username}」的第 1 天（初始建立基準）。
目前總持股數: {stats['total_today']} 檔。
前五大持股: {', '.join(top5)}。

請輸出一段 100~130 字的繁體中文簡短總結：
1. 說明已完成建立 {username} 當前 {stats['total_today']} 檔持股的基準追蹤。
2. 簡要點評前幾大重倉配置方向（例如以科技巨頭、大盤指數與主題板塊為主）。
3. 說明明日起將自動追蹤每日調倉增減。
直接輸出繁體中文段落即可。
"""
    else:
        prompt_context = []
        prompt_context.append(f"投資者名稱: {username}")
        prompt_context.append(f"當前總持股數: {stats['total_today']}")
        
        if stats["new_symbols"]:
            new_list = [f"{c['symbol']} (佔比: {c['today_alloc']}%)" for c in changes if c["status"] == "NEW"]
            prompt_context.append(f"新開倉標的 (New): {', '.join(new_list)}")

        if stats["closed_symbols"]:
            closed_list = [f"{c['symbol']} (原佔比: {c['yesterday_alloc']}%)" for c in changes if c["status"] == "CLOSED"]
            prompt_context.append(f"已清倉/平倉標的 (Closed): {', '.join(closed_list)}")

        inc_list = [f"{c['symbol']} (增幅: +{c['diff']}%, 現佔比: {c['today_alloc']}%)" for c in changes if c["status"] == "INCREASED"]
        if inc_list:
            prompt_context.append(f"加碼標的: {', '.join(inc_list)}")

        dec_list = [f"{c['symbol']} (降幅: {c['diff']}%, 現佔比: {c['today_alloc']}%)" for c in changes if c["status"] == "DECREASED"]
        if dec_list:
            prompt_context.append(f"減碼標的: {', '.join(dec_list)}")

        top3 = [f"{p['symbol']} ({p['allocation']}%)" for p in analysis_result["today_portfolio"][:3]]
        prompt_context.append(f"當前持股前三大: {', '.join(top3)}")

        prompt = f"""
你是一位專業的美股與投資組合分析師。請根據以下 eToro 明星投資者「{username}」的今日持股與調倉變動數據，撰寫一段 100~150 字的結構化繁體中文每日調倉總結。

【調倉數據】:
{chr(10).join(prompt_context)}

【輸出要求】:
1. 嚴格使用繁體中文（台灣習慣用語，如：加碼、減碼、開倉、平倉、部位）。
2. 字數控制在 100 ~ 150 字之間，簡練有力。
3. 結構清楚：包含【今日調倉焦點】與【策略觀點】。
4. 若無任何重大變動，請指出整體配置持穩及目前主力重倉板塊。
5. 直接輸出繁體中文摘要段落。
"""

    rest_result = _call_gemini_rest_api(prompt, api_key)
    if rest_result:
        logger.info("成功透過 Gemini REST API 獲得調倉摘要！")
        return rest_result

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        if response and response.text:
            return response.text.strip()
    except Exception as e:
        logger.debug(f"SDK 調用跳過: {e}")

    logger.warning("Gemini 呼叫未取得回應，切換至 Fallback 摘要。")
    return generate_fallback_summary(analysis_result, username)
