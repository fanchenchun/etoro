"""
AI 智能摘要模組 (Gemini Flash & 智慧型規則引擎)
生成結構化繁體中文調倉總結，兼具精確變動數據與深度板塊輪動策略洞見。
支援:
1. Google 官方 Gemini REST API (具備完整 multi-part 拼接、過濾思維鏈、健全長度檢驗)
2. google-generativeai SDK (若已安裝則可選用)
3. 智慧型規則引擎 Fallback (自動比對產業板塊、資金流向與動態策略評論，確保無 Key 或異常時仍具深度洞見)
"""

import os
import sys
import json
import logging
import requests
from typing import Dict, Any, Optional, List

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger(__name__)

# 標的產業板塊與業務資訊字典 (涵蓋 miulatw 持倉與美股常見標的)
SECTOR_INFO: Dict[str, Dict[str, str]] = {
    "AAPL": {"name": "蘋果", "sector": "科技巨頭", "desc": "消費電子與服務生態"},
    "ACHR": {"name": "Archer Aviation", "sector": "低空經濟", "desc": "eVTOL電動垂直起降飛行器"},
    "AMZN": {"name": "亞馬遜", "sector": "科技巨頭", "desc": "雲端運算AWS與電商"},
    "ANET": {"name": "Arista Networks", "sector": "雲端網通", "desc": "AI資料中心高速交換機"},
    "AVGO": {"name": "博通", "sector": "半導體", "desc": "客製化AI ASIC晶片與網通"},
    "BTC": {"name": "比特幣", "sector": "數位資產", "desc": "加密貨幣與數位黃金"},
    "COHR": {"name": "Coherent", "sector": "光通訊", "desc": "高速光收發模組與雷射光電"},
    "COPX": {"name": "銅礦ETF", "sector": "關鍵原物料", "desc": "電網與AI基建關鍵銅礦ETF"},
    "CRDO": {"name": "Credo", "sector": "高速傳輸晶片", "desc": "AI資料中心高速連接與DSP晶片"},
    "CRWD": {"name": "CrowdStrike", "sector": "資安防禦", "desc": "雲端端點安全平台"},
    "ETN": {"name": "伊頓", "sector": "電氣基建", "desc": "資料中心電力管理與配電系統"},
    "ETOR": {"name": "eToro", "sector": "金融科技", "desc": "社群投資交易平台"},
    "GEV": {"name": "GE Vernova", "sector": "能源電網", "desc": "電力發電設備與智慧電網"},
    "GOOG": {"name": "Alphabet (Google)", "sector": "科技巨頭", "desc": "搜尋引擎、AI與雲端"},
    "INTC": {"name": "英特爾", "sector": "半導體", "desc": "處理器與晶圓製造"},
    "KTOS": {"name": "Kratos Defense", "sector": "國防軍工", "desc": "軍用無人機與衛星通訊系統"},
    "LITE": {"name": "Lumentum", "sector": "光通訊", "desc": "光學元件與雷射光收發模組"},
    "META": {"name": "Meta", "sector": "科技巨頭", "desc": "社群平台與開源AI生態"},
    "MP": {"name": "MP Materials", "sector": "關鍵原物料", "desc": "稀土磁鐵材料"},
    "MSFT": {"name": "微軟", "sector": "科技巨頭", "desc": "企業雲端Azure與生成式AI"},
    "MU": {"name": "美光科技", "sector": "記憶體", "desc": "高頻寬記憶體HBM與DRAM"},
    "NET": {"name": "Cloudflare", "sector": "雲端資安", "desc": "邊緣運算與網路安全防護"},
    "NFLX": {"name": "Netflix", "sector": "數位娛樂", "desc": "全球串流影音龍頭"},
    "NVDA": {"name": "輝達", "sector": "AI晶片", "desc": "GPU加速運算與AI生態霸主"},
    "PANW": {"name": "Palo Alto Networks", "sector": "資安防禦", "desc": "新世代企業網路與雲端資安"},
    "PLTR": {"name": "Palantir", "sector": "AI國防軟體", "desc": "AI企業營運系統與國防大數據分析"},
    "QQQ": {"name": "Invesco QQQ", "sector": "大盤指數ETF", "desc": "那斯達克100指數ETF"},
    "RDW": {"name": "Redwire", "sector": "太空軍工", "desc": "太空基礎設施與在軌製造"},
    "ROK": {"name": "羅克韋爾", "sector": "工業自動化", "desc": "智慧製造與工業數位化"},
    "SE": {"name": "Sea Limited", "sector": "電商金融", "desc": "東南亞電商蝦皮與數位金融"},
    "SERVICENOW": {"name": "ServiceNow", "sector": "企業軟體", "desc": "IT服務自動化雲端平台"},
    "SKHYNIX": {"name": "SK海力士", "sector": "記憶體", "desc": "AI伺服器高頻寬記憶體HBM"},
    "SLV": {"name": "白銀ETF", "sector": "貴金屬原物料", "desc": "抗通膨與工業光伏白銀ETF"},
    "SPACEX": {"name": "SpaceX", "sector": "太空航太", "desc": "可重複使用火箭與星鏈衛星通訊"},
    "STX": {"name": "希捷科技", "sector": "資料儲存", "desc": "大容量機械硬碟HDD儲存"},
    "TER": {"name": "泰瑞達", "sector": "半導體設備", "desc": "自動化晶片測試設備與協作機器人"},
    "TSLA": {"name": "特斯拉", "sector": "電動車/自駕", "desc": "電動車、FSD自駕與人形機器人"},
    "TSM": {"name": "台積電 ADR", "sector": "晶圓代工", "desc": "全球先進製程晶圓代工龍頭"},
    "VRT": {"name": "維諦技術", "sector": "AI伺服器散熱", "desc": "資料中心電力管理與液冷散熱"},
    "XLV": {"name": "醫療保健ETF", "sector": "防禦型醫療", "desc": "美國生技醫療權值ETF"},
    "ENERGY": {"name": "能源類股ETF", "sector": "傳統能源", "desc": "石油與天然氣板塊"},
}


def generate_fallback_summary(
    analysis_result: Dict[str, Any],
    username: str = "miulatw",
    cash_balance: Optional[Dict[str, Any]] = None
) -> str:
    """
    當無 API Key 或調用失敗時的智慧型規則引擎摘要
    具備標的板塊識別、增減比例數據精確條列與市場輪動策略洞見。
    """
    stats = analysis_result["stats"]
    changes = analysis_result["changes"]

    if stats.get("is_first_day"):
        top5 = [f"{c['symbol']}({c['today_alloc']}%)" for c in changes[:5]]
        return (
            f"【建立持倉基準】{username} 目前投資組合共持有 {stats['total_today']} 檔美股與 ETF 標的。\n"
            f"前五大核心重倉依序為：{'、'.join(top5)}。\n"
            f"系統已建立今日歷史基準快照，自下一個交易日起將每日自動追蹤比對調倉增減與新開平倉動作。"
        )

    if not stats.get("has_significant_changes"):
        top3 = [f"{p['symbol']} ({p['allocation']}%)" for p in analysis_result.get("today_portfolio", [])[:3]]
        top_str = f"目前前三大核心配置為：{'、'.join(top3)}。" if top3 else ""
        return f"【今日持倉持穩】{username} 今日投資組合維持穩定，各主要美股持倉比重未見顯著增減，整體維持原有之科技巨頭與主題成長股長期配置架構。{top_str}"

    focus_lines = []

    # 1. 新開倉
    new_items = [c for c in changes if c["status"] == "NEW"]
    if new_items:
        new_strs = [
            f"{c['symbol']} ({SECTOR_INFO.get(c['symbol'], {}).get('name', c['name'])}, 佔比 {c['today_alloc']}%)"
            for c in new_items
        ]
        focus_lines.append(f"• 新開倉：{', '.join(new_strs)}")

    # 2. 全數平倉
    closed_items = [c for c in changes if c["status"] == "CLOSED"]
    if closed_items:
        closed_strs = [
            f"{c['symbol']} ({SECTOR_INFO.get(c['symbol'], {}).get('name', c['name'])}, 原佔比 {c['yesterday_alloc']}%)"
            for c in closed_items
        ]
        focus_lines.append(f"• 全數平倉：{', '.join(closed_strs)}")

    # 3. 加碼 (按增幅由大至小排序)
    inc_items = [c for c in changes if c["status"] == "INCREASED"]
    inc_items.sort(key=lambda x: x.get("diff", 0), reverse=True)
    if inc_items:
        inc_strs = [
            f"{c['symbol']} (+{c['diff']}% ➔ {c['today_alloc']}%)"
            for c in inc_items
        ]
        focus_lines.append(f"• 加碼：{', '.join(inc_strs)}")

    # 4. 減碼 (按減幅由大至小排序)
    dec_items = [c for c in changes if c["status"] == "DECREASED"]
    dec_items.sort(key=lambda x: x.get("diff", 0))
    if dec_items:
        dec_strs = [
            f"{c['symbol']} ({c['diff']}% ➔ {c['today_alloc']}%)"
            for c in dec_items
        ]
        focus_lines.append(f"• 減碼：{', '.join(dec_strs)}")

    # --- 深度策略洞見與板塊輪動分析 ---
    inc_sectors = [SECTOR_INFO.get(c["symbol"], {}).get("sector", "特定題材") for c in inc_items]
    dec_sectors = [SECTOR_INFO.get(c["symbol"], {}).get("sector", "特定板塊") for c in dec_items]

    insights = []
    # 科技巨頭/AI晶片調節，轉向垂直題材
    if any(s in dec_sectors for s in ["科技巨頭", "AI晶片"]) and any(s in inc_sectors for s in ["資安防禦", "AI國防軟體", "高速傳輸晶片", "太空航太", "記憶體", "雲端資安"]):
        inc_names = [f"{SECTOR_INFO.get(c['symbol'], {}).get('sector', '')} {c['symbol']}" for c in inc_items]
        dec_names = [c['symbol'] for c in dec_items if SECTOR_INFO.get(c['symbol'], {}).get('sector') in ["科技巨頭", "AI晶片"]]
        insights.append(
            f"資金明顯呈現「權值巨頭獲利調節，轉進高動能垂直賽道」。"
            f"投資人適度減碼了大型巨頭與晶片股 ({', '.join(dec_names)})，"
            f"將資金精準分流至 {'、'.join(inc_names)}。"
        )
    elif dec_items and inc_items:
        inc_top = ', '.join([c['symbol'] for c in inc_items[:3]])
        dec_top = ', '.join([c['symbol'] for c in dec_items[:3]])
        insights.append(
            f"整體部位呈現結構性輪動，資金自 {dec_top} 等標的適度調節，"
            f"聚焦增持強勢進攻標的 {inc_top}。"
        )
    elif new_items:
        new_top = ', '.join([c['symbol'] for c in new_items[:2]])
        insights.append(f"今日積極建立新戰略倉位 ({new_top})，拓展投資組合配置廣度。")
    elif closed_items:
        closed_top = ', '.join([c['symbol'] for c in closed_items[:2]])
        insights.append(f"全數出清獲利了結或調整策略之標的 ({closed_top})，精簡持股組合。")

    insights.append(
        f"目前總持股維持 {stats['total_today']} 檔，在控制標的數量的同時持續優化內部比重。"
    )

    if cash_balance:
        avail_cash = cash_balance.get("available_cash_pct")
        if avail_cash is not None:
            cash_diff = cash_balance.get("diff", 0.0)
            diff_desc = f" (變動 {cash_diff:+.2f}%)" if cash_diff != 0 else ""
            insights.append(f"未投資現金水位為 {avail_cash}%{diff_desc}，整體部位攻守兼備並保留充裕機動性。")

    summary_text = (
        f"【今日調倉焦點】\n"
        f"{chr(10).join(focus_lines)}\n\n"
        f"【策略觀點與板塊輪動】\n"
        f"{''.join(insights)}"
    )
    return summary_text


def _call_gemini_rest_api(prompt: str, api_key: str) -> Optional[str]:
    """
    直接透過 Google Gemini 官方 REST API 呼叫 Gemini Flash 模型
    (具備完整 multi-part 拼接、過濾思維鏈、健全長度檢驗與多版本模型輪替)
    """
    models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
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
            "maxOutputTokens": 1024
        }
    }

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=25)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    text_parts = []
                    for p in parts:
                        if isinstance(p, dict) and not p.get("thought", False):
                            t = p.get("text", "")
                            if t:
                                text_parts.append(t)
                    full_text = "".join(text_parts).strip()
                    # 健全性檢驗：字數需大於 50 字且非僅有殘缺標題
                    if len(full_text) >= 50 and not full_text.endswith("總結】") and not full_text.endswith("調倉總結"):
                        return full_text
                    else:
                        logger.warning(f"Gemini REST API ({model_name}) 回傳文本過短或殘缺 ({len(full_text)} 字元)，嘗試下一個模型...")
            else:
                logger.warning(f"Gemini REST API ({model_name}) 回應狀態碼 {res.status_code}: {res.text[:160]}")
        except Exception as e:
            logger.warning(f"Gemini REST API ({model_name}) 請求例外: {e}")

    return None


def generate_ai_summary(
    analysis_result: Dict[str, Any],
    username: str = "miulatw",
    api_key: Optional[str] = None,
    cash_balance: Optional[Dict[str, Any]] = None
) -> str:
    """
    呼叫 Gemini API 產生繁體中文分析摘要，未設定 Key 或調用失敗時自動切換至深度規則引擎
    """
    api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("未偵測到 GEMINI_API_KEY，啟用規則型深度摘要生成。")
        return generate_fallback_summary(analysis_result, username, cash_balance=cash_balance)

    stats = analysis_result["stats"]
    changes = analysis_result["changes"]

    if stats.get("is_first_day"):
        top5 = [f"{c['symbol']} ({c['today_alloc']}%)" for c in changes[:5]]
        prompt = f"""
你是一位專業的美股投資分析師。這是追蹤 eToro 明星投資者「{username}」的第 1 天（初始建立基準）。
目前總持股數: {stats['total_today']} 檔。
前五大持股: {', '.join(top5)}。

請輸出一段 120~160 字的繁體中文簡短總結：
1. 說明已完成建立 {username} 當前 {stats['total_today']} 檔持股的基準追蹤。
2. 簡要點評前幾大重倉配置方向（例如以科技巨頭、大盤指數與主題板塊為主）。
3. 說明明日起將自動追蹤每日調倉增減。
直接輸出繁體中文段落即可。
"""
    else:
        prompt_context = []
        prompt_context.append(f"投資者名稱: {username}")
        prompt_context.append(f"當前總持股數: {stats['total_today']} 檔")
        if cash_balance:
            avail = cash_balance.get("available_cash_pct", "")
            diff_c = cash_balance.get("diff", 0.0)
            prompt_context.append(f"未投資現金比例: {avail}% (vs昨日變動: {diff_c:+.2f}%)")

        if stats["new_symbols"]:
            new_list = [
                f"{c['symbol']} ({SECTOR_INFO.get(c['symbol'], {}).get('name', c['name'])}, 領域: {SECTOR_INFO.get(c['symbol'], {}).get('sector', '其他')}, 佔比: {c['today_alloc']}%)"
                for c in changes if c["status"] == "NEW"
            ]
            prompt_context.append(f"新開倉標的: {', '.join(new_list)}")

        if stats["closed_symbols"]:
            closed_list = [
                f"{c['symbol']} ({SECTOR_INFO.get(c['symbol'], {}).get('name', c['name'])}, 領域: {SECTOR_INFO.get(c['symbol'], {}).get('sector', '其他')}, 原佔比: {c['yesterday_alloc']}%)"
                for c in changes if c["status"] == "CLOSED"
            ]
            prompt_context.append(f"已清倉標的: {', '.join(closed_list)}")

        inc_list = [
            f"{c['symbol']} ({SECTOR_INFO.get(c['symbol'], {}).get('name', c['name'])}, 領域: {SECTOR_INFO.get(c['symbol'], {}).get('sector', '其他')}, 增幅: +{c['diff']}%, 現佔比: {c['today_alloc']}%)"
            for c in changes if c["status"] == "INCREASED"
        ]
        if inc_list:
            prompt_context.append(f"加碼標的: {'; '.join(inc_list)}")

        dec_list = [
            f"{c['symbol']} ({SECTOR_INFO.get(c['symbol'], {}).get('name', c['name'])}, 領域: {SECTOR_INFO.get(c['symbol'], {}).get('sector', '其他')}, 降幅: {c['diff']}%, 現佔比: {c['today_alloc']}%)"
            for c in changes if c["status"] == "DECREASED"
        ]
        if dec_list:
            prompt_context.append(f"減碼標的: {'; '.join(dec_list)}")

        top3 = [f"{p['symbol']} ({p['allocation']}%)" for p in analysis_result["today_portfolio"][:3]]
        prompt_context.append(f"當前持股前三大重倉: {', '.join(top3)}")

        prompt = f"""
你是一位專業的美股與投資組合策略分析師。請根據以下 eToro 明星投資者「{username}」的今日持股與調倉數據，撰寫一段具備深度洞見、結構清晰的繁體中文每日調倉總結。

【調倉數據】:
{chr(10).join(prompt_context)}

【輸出要求】:
1. 嚴格使用繁體中文（台灣習慣用語，如：加碼、減碼、開倉、平倉、部位、獲利了結、板塊輪動）。
2. 請務必按照以下兩個結構化區塊輸出：
   【今日調倉焦點】
   條列今日所有操作之標的代號、中文名稱、變動幅度 (Δ%) 與調整後佔比（例如：加碼 PANW (+0.07% ➔ 2.51%)）。
   【策略觀點與板塊輪動】
   深入點評資金流向背後的具體策略（例如：分析資金是由哪些板塊/巨頭獲利調節流出、轉向加碼哪些高動能關鍵賽道；整體進攻與防守姿態、現金水位的意涵）。
3. 絕不可給予泛泛而談的籠統套話，務必具體結合今日有變動的標的產業背景與數據進行深度解析。
4. 控制在 150 ~ 250 字之間，排版清晰易讀，直接輸出繁體中文總結段落。
"""

    rest_result = _call_gemini_rest_api(prompt, api_key)
    if rest_result:
        logger.info("成功透過 Gemini REST API 獲得調倉摘要！")
        return rest_result

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        for model_name in ["gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                if response and response.text:
                    txt = response.text.strip()
                    if len(txt) >= 50 and not txt.endswith("總結】") and not txt.endswith("調倉總結"):
                        return txt
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"SDK 調用跳過: {e}")

    logger.warning("Gemini 呼叫未取得回應或回傳不完整，切換至智慧型規則引擎 Fallback 摘要。")
    return generate_fallback_summary(analysis_result, username, cash_balance=cash_balance)

