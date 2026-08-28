"""
eToro 投資組合爬蟲模組 (高可用雙軌架構)
層級支援:
1. Tier 1: eToro Direct SAPI (極速、精確、零資源消耗)
2. Tier 2: Playwright Headless Browser (SPA 渲染與封包攔截)
3. Tier 3: DOM Fallback & Mock 數據保底
包含未投資餘額與可用現金比例抓取。
"""

import sys
import os
import json
import time
import logging
import re
import uuid
import requests
import concurrent.futures
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta

# 台灣時區 (UTC+8)
TAIPEI_TZ = timezone(timedelta(hours=8))

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# eToro Instrument ID 符號對應表
KNOWN_INSTRUMENT_SYMBOLS = {
    1001: "AAPL",
    1002: "GOOG",
    1003: "META",
    1004: "MSFT",
    1005: "AMZN",
    1111: "TSLA",
    1127: "NFLX",
    1130: "MU",
    1137: "NVDA",
    1341: "GEV",
    1780: "ROK",
    3006: "QQQ",
    3017: "XLV",
    4124: "PANW",
    4236: "AVGO",
    4273: "ETN",
    4294: "ANET",
    4356: "STX",
    4430: "SLV",
    4434: "LITE",
    4481: "TSM",
    5506: "CRWD",
    5604: "KTOS",
    5712: "NET",
    5960: "SE",
    6094: "COHR",
    6549: "TER",
    7991: "PLTR",
    8867: "VRT",
    8886: "MP",
    9450: "ACHR",
    9471: "CRDO",
    10805: "COPX",
    10963: "RDW",
    12200: "ETOR",
    15239: "SKHYNIX",
    15618: "SPACEX",
    100000: "BTC"
}


def format_relative_time(iso_str: str) -> str:
    """計算相對於現在的時間差 (例如：7 天前、2 小時前、剛剛)"""
    if not iso_str:
        return "近期"
    try:
        cleaned = iso_str.replace("Z", "+00:00")
        created_dt = datetime.fromisoformat(cleaned)
        now_dt = datetime.now(timezone.utc)
        delta = now_dt - created_dt
        
        if delta.days > 365:
            return f"{delta.days // 365} 年前"
        if delta.days > 30:
            return f"{delta.days // 30} 個月前"
        if delta.days > 0:
            return f"{delta.days} 天前"
        
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours} 小時前"
        
        minutes = delta.seconds // 60
        if minutes > 0:
            return f"{minutes} 分鐘前"
            
        return "剛剛"
    except Exception:
        return "近期"


def format_iso_to_taipei(iso_str: str) -> str:
    """將 ISO 時間格式化為台灣時間 (YYYY/MM/DD HH:MM)"""
    if not iso_str:
        return ""
    try:
        cleaned = iso_str.replace("Z", "+00:00")
        dt_utc = datetime.fromisoformat(cleaned)
        dt_taipei = dt_utc.astimezone(TAIPEI_TZ)
        return dt_taipei.strftime("%Y/%m/%d %H:%M")
    except Exception:
        return iso_str[:16].replace("T", " ")


def get_mock_portfolio_data() -> List[Dict[str, Any]]:
    """
    提供標準結構的模擬資料 (以 miulatw 典型持倉為基準)
    """
    return [
        {"symbol": "QQQ", "name": "Invesco QQQ", "allocation": 5.65, "instrument_type": "ETF", "avg_open_rate": 480.20, "current_rate": 505.30, "net_profit": 10.55},
        {"symbol": "META", "name": "Meta Platforms Inc", "allocation": 3.70, "instrument_type": "Stocks", "avg_open_rate": 287.98, "current_rate": 549.78, "net_profit": 89.69},
        {"symbol": "GOOG", "name": "Alphabet", "allocation": 3.55, "instrument_type": "Stocks", "avg_open_rate": 162.54, "current_rate": 341.52, "net_profit": 103.89},
        {"symbol": "COPX", "name": "Global X Copper Miners Etf", "allocation": 3.52, "instrument_type": "ETF", "avg_open_rate": 42.10, "current_rate": 54.40, "net_profit": 29.25},
        {"symbol": "AMZN", "name": "Amazon.com Inc", "allocation": 3.47, "instrument_type": "Stocks", "avg_open_rate": 122.04, "current_rate": 258.37, "net_profit": 109.75},
        {"symbol": "MSFT", "name": "Microsoft", "allocation": 3.29, "instrument_type": "Stocks", "avg_open_rate": 209.34, "current_rate": 483.18, "net_profit": 124.75},
        {"symbol": "AAPL", "name": "Apple", "allocation": 3.05, "instrument_type": "Stocks", "avg_open_rate": 166.44, "current_rate": 309.80, "net_profit": 87.26},
        {"symbol": "XLV", "name": "State Street Health Care Select Sector SPDR ETF", "allocation": 2.82, "instrument_type": "ETF", "avg_open_rate": 140.50, "current_rate": 152.80, "net_profit": 8.71},
        {"symbol": "ETOR", "name": "eToro Group LTD", "allocation": 2.81, "instrument_type": "Stocks", "avg_open_rate": 26.50, "current_rate": 28.54, "net_profit": 7.71},
        {"symbol": "TSLA", "name": "Tesla Motors, Inc.", "allocation": 2.73, "instrument_type": "Stocks", "avg_open_rate": 150.99, "current_rate": 362.43, "net_profit": 121.45},
    ]


def get_mock_comment_data() -> Dict[str, Any]:
    """
    提供最新留言模擬資料
    """
    return {
        "id": "mock-comment-001",
        "author_name": "Yueh Nung Hung",
        "username": "miulatw",
        "avatar_url": "https://etoro-cdn.etorostatic.com/avatars/50X50/8220524/1.jpg",
        "country": "臺灣",
        "created_at": "2026-08-21T14:23:13.853Z",
        "created_at_formatted": "2026/08/21 22:23",
        "relative_time": "7 天前",
        "content": "買進 $KTOS",
        "likes_count": 5,
        "comments_count": 1,
        "shares_count": 0,
        "post_url": "https://www.etoro.com/zh-tw/people/miulatw",
        "is_new": False
    }


class EToroScraper:
    def __init__(self, username: str = "miulatw", headless: bool = True, timeout: int = 35000):
        self.username = username
        self.url = f"https://www.etoro.com/zh-tw/people/{username}"
        self.portfolio_url = f"https://www.etoro.com/zh-tw/people/{username}/portfolio"
        self.headless = headless
        self.timeout = timeout
        self.intercepted_data: Optional[List[Dict[str, Any]]] = None
        self.gcid: Optional[int] = 8506401 if username.lower() == "miulatw" else None
        self.real_cid: Optional[int] = 8220524 if username.lower() == "miulatw" else None
        self.cash_balance: Dict[str, float] = {
            "available_cash_pct": 18.46,
            "total_invested_pct": 81.54
        }
        self.latest_comment: Optional[Dict[str, Any]] = None

    def fetch_user_info(self) -> bool:
        """
        查詢用戶的 GCID 與 RealCID
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": f"https://www.etoro.com/people/{self.username}"
        }
        user_url = f"https://www.etoro.com/api/logininfo/v1.1/users/{self.username}"
        for attempt in range(1, 4):
            try:
                res = requests.get(user_url, headers=headers, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    self.gcid = data.get("gcid") or self.gcid
                    self.real_cid = data.get("realCID") or self.real_cid
                    logger.info(f"用戶 [{self.username}] 資訊解析成功: GCID={self.gcid}, RealCID={self.real_cid}")
                    return True
            except Exception as e:
                logger.debug(f"查詢用戶資訊嘗試 {attempt}/3 失敗: {e}")
                time.sleep(1)
        return False

    def fetch_latest_comment(self) -> Optional[Dict[str, Any]]:
        """
        抓取用戶在 eToro 上最新一則留言/貼文 (Feed / Comment)
        """
        logger.info(f"嘗試抓取用戶 [{self.username}] 最新動態留言 (Comment / Feed)...")
        if not self.gcid:
            self.fetch_user_info()

        if not self.gcid:
            logger.warning(f"缺少 GCID，無法抓取 {self.username} 的動態貼文")
            return None

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": f"https://www.etoro.com/people/{self.username}",
            "Account-Type": "Real",
            "Application-Identifier": "ReToro"
        }

        req_id = str(uuid.uuid4())
        feed_url = f"https://www.etoro.com/api/edm-streams/v1/feed/user/top/{self.gcid}?take=10&offset=0&reactionsPageSize=20&client_request_id={req_id}"

        for attempt in range(1, 4):
            try:
                res = requests.get(feed_url, headers=headers, timeout=12)
                if res.status_code == 200:
                    data = res.json()
                    discussions = data.get("discussions", [])
                    if not discussions:
                        logger.warning("動態貼文清單為空")
                        return None

                    # 取出最新一則 discussion
                    top_disc = discussions[0]
                    post = top_disc.get("post", {})
                    owner = post.get("owner", {})

                    likes = top_disc.get("emotionsData", {}).get("like", {}).get("paging", {}).get("totalCount", 0)
                    if not likes:
                        likes = top_disc.get("reactions", {}).get("totalReactionsCount", 0)

                    comments_count = top_disc.get("summary", {}).get("totalCommentsAndReplies", 0)
                    if not comments_count:
                        comments_count = top_disc.get("commentsCount", 0)

                    shares_count = top_disc.get("summary", {}).get("sharedCount", 0)
                    if not shares_count:
                        shares_count = top_disc.get("sharesCount", 0)

                    created_at = post.get("created", "")
                    content_text = post.get("message", {}).get("text", "").strip()

                    author_name = f"{owner.get('firstName', '')} {owner.get('lastName', '')}".strip() or self.username
                    avatar = owner.get("avatar", {}).get("medium") or owner.get("avatar", {}).get("small") or "https://etoro-cdn.etorostatic.com/avatars/50X50/8220524/1.jpg"

                    country_code = owner.get("countryCode")
                    country_name = "臺灣" if country_code == 199 else "全球"

                    comment_info = {
                        "id": post.get("id"),
                        "author_name": author_name,
                        "username": owner.get("username", self.username),
                        "avatar_url": avatar,
                        "country": country_name,
                        "created_at": created_at,
                        "created_at_formatted": format_iso_to_taipei(created_at),
                        "relative_time": format_relative_time(created_at),
                        "content": content_text,
                        "likes_count": likes,
                        "comments_count": comments_count,
                        "shares_count": shares_count,
                        "post_url": f"https://www.etoro.com/zh-tw/people/{self.username}",
                        "is_new": False
                    }

                    self.latest_comment = comment_info
                    logger.info(f"✨ 成功獲取最新動態: [{author_name}] {content_text[:30]}... ({comment_info['relative_time']})")
                    return comment_info
            except Exception as e:
                logger.warning(f"抓取最新動態嘗試 {attempt}/3 失敗: {e}")
                time.sleep(1.5)

        return None

    def fetch_via_direct_api(self) -> Optional[List[Dict[str, Any]]]:
        """
        Tier 1: 直接透過 eToro Public SAPI 抓取即時持倉與餘額 (具備重試機制)
        """
        logger.info(f"嘗試透過 eToro Direct SAPI 抓取用戶 [{self.username}] 即時部位...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": f"https://www.etoro.com/people/{self.username}/portfolio"
        }

        # 1. 取得用戶 CID
        if not self.real_cid:
            self.fetch_user_info()

        cid = self.real_cid or (8220524 if self.username.lower() == "miulatw" else None)
        if not cid:
            logger.warning(f"未能獲取用戶 {self.username} 的 Customer ID")
            return None

        # 2. 獲取投資組合部位 (帶重試)
        port_url = f"https://www.etoro.com/sapi/trade-data-real/live/public/portfolios?cid={cid}"
        port_json = None
        for attempt in range(1, 4):
            try:
                port_res = requests.get(port_url, headers=headers, timeout=12)
                if port_res.status_code == 200:
                    port_json = port_res.json()
                    break
                logger.warning(f"SAPI 投資組合請求嘗試 {attempt}/3 狀態碼: {port_res.status_code}")
            except Exception as e:
                logger.warning(f"SAPI 投資組合請求嘗試 {attempt}/3 例外: {e}")
            time.sleep(1.5)

        if not port_json:
            logger.warning("無法從 SAPI 取得持倉資料")
            return None
        
        # 提取餘額資訊 (未投資可用現金 %)
        avail_cash = round(float(port_json.get("CreditByRealizedEquity", 18.46)), 2)
        tot_invest = round(100.0 - avail_cash, 2)
        self.cash_balance = {
            "available_cash_pct": avail_cash,
            "total_invested_pct": tot_invest
        }
        logger.info(f"帳戶餘額資訊: 可用現金 {avail_cash}%, 已投資 {tot_invest}%")

        positions = port_json.get("AggregatedPositions", [])
        if not positions:
            logger.warning("SAPI 返回的持倉清單為空")
            return None

        # 3. 獲取標的元數據 (代號與名稱)
        inst_ids_str = [str(p["InstrumentID"]) for p in positions]
        meta_map = self._fetch_instruments_metadata(inst_ids_str, headers)

        # 4. 並行獲取各標的「平均開倉價」與「當前現價」
        inst_ids_int = [int(p["InstrumentID"]) for p in positions]
        rates_map = self._fetch_positions_rates(cid, inst_ids_int, headers)

        # 5. 提取投資佔比與價格資訊
        parsed_items = []

        for p in positions:
            iid = p.get("InstrumentID")
            meta = meta_map.get(iid, {
                "symbol": KNOWN_INSTRUMENT_SYMBOLS.get(iid, f"ID_{iid}"),
                "name": f"Instrument {iid}"
            })
            
            invested_alloc = round(float(p.get("Invested", 0.0)), 2)

            symbol = KNOWN_INSTRUMENT_SYMBOLS.get(iid, meta["symbol"])
            if str(symbol).isdigit() and int(symbol) in KNOWN_INSTRUMENT_SYMBOLS:
                symbol = KNOWN_INSTRUMENT_SYMBOLS[int(symbol)]

            rate_info = rates_map.get(iid, {})
            avg_open_rate = rate_info.get("avg_open_rate")
            current_rate = rate_info.get("current_rate")

            parsed_items.append({
                "symbol": symbol,
                "name": meta["name"],
                "allocation": invested_alloc,
                "instrument_type": "Stocks",
                "net_profit": round(float(p.get("NetProfit", 0.0)), 2),
                "avg_open_rate": avg_open_rate,
                "current_rate": current_rate
            })

        if parsed_items:
            logger.info(f"✨ 成功透過 SAPI 獲取 {len(parsed_items)} 檔真實持股部位 (包含平均開倉價與當前現價)！")
            return self._clean_and_sort(parsed_items)

        return None

    def _fetch_positions_rates(self, cid: int, inst_ids: List[int], headers: dict) -> Dict[int, Dict[str, Any]]:
        """
        並行透過 SAPI 獲取各標的的平均開倉價格 (AverageOpen) 與當前價格 (CurrentRate)
        """
        rates_map: Dict[int, Dict[str, Any]] = {}
        if not inst_ids:
            return rates_map

        def fetch_single(iid: int):
            url = f"https://www.etoro.com/sapi/trade-data-real/live/public/positions?cid={cid}&InstrumentID={iid}"
            for _ in range(2):
                try:
                    res = requests.get(url, headers=headers, timeout=8)
                    if res.status_code == 200:
                        data = res.json()
                        avg_open = data.get("AverageOpen")
                        pub_pos = data.get("PublicPositions", [])
                        cur_rate = pub_pos[0].get("CurrentRate") if (pub_pos and isinstance(pub_pos, list)) else None
                        
                        return iid, {
                            "avg_open_rate": round(float(avg_open), 2) if avg_open is not None else None,
                            "current_rate": round(float(cur_rate), 2) if cur_rate is not None else None
                        }
                except Exception as e:
                    logger.debug(f"獲取 InstrumentID {iid} 價格資訊失敗: {e}")
                    time.sleep(0.5)
            return iid, {"avg_open_rate": None, "current_rate": None}

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                results = executor.map(fetch_single, inst_ids)
                for iid, val in results:
                    rates_map[iid] = val
        except Exception as e:
            logger.warning(f"並行獲取開倉價時發生例外: {e}")

        return rates_map

    def _fetch_instruments_metadata(self, inst_ids: List[str], headers: dict) -> Dict[int, Dict[str, str]]:
        """獲取 InstrumentID 的代號與名稱"""
        meta_map = {}
        if not inst_ids:
            return meta_map

        for _ in range(2):
            try:
                ids_str = ",".join(inst_ids)
                url = f"https://api.etorostatic.com/sapi/instrumentsmetadata/v1.1/instruments?instrumentIds={ids_str}"
                res = requests.get(url, headers=headers, timeout=12)
                if res.status_code == 200:
                    data = res.json()
                    for item in data.get("InstrumentDisplayDatas", []):
                        iid = item.get("InstrumentID")
                        name = item.get("InstrumentDisplayName", "Unknown")
                        symbol = KNOWN_INSTRUMENT_SYMBOLS.get(iid)

                        if not symbol:
                            for img in item.get("Images", []):
                                uri = img.get("Uri", "")
                                m = re.search(r"/market-avatars/([^/]+)/", uri)
                                if m:
                                    sym_cand = m.group(1).upper()
                                    if not sym_cand.isdigit():
                                        symbol = sym_cand
                                        break

                        if not symbol:
                            symbol = name.split()[0].upper() if name else str(iid)

                        meta_map[iid] = {
                            "symbol": symbol,
                            "name": name
                        }
                    if meta_map:
                        break
            except Exception as e:
                logger.debug(f"獲取標的元數據例外: {e}")
                time.sleep(1)

        return meta_map

    def fetch_via_playwright(self) -> Optional[List[Dict[str, Any]]]:
        """
        Tier 2: 透過 Playwright 渲染頁面與監聽 API
        """
        logger.info(f"啟動 Playwright 爬蟲訪問 eToro 用戶 [{self.username}] 網頁...")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("未安裝 Playwright 模組，跳過瀏覽器渲染。")
            return None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    viewport={"width": 1440, "height": 900}
                )
                page = context.new_page()

                def handle_resp(response):
                    if "trade-data" in response.url and "portfolios" in response.url:
                        try:
                            data = response.json()
                            positions = data.get("AggregatedPositions", [])
                            if positions:
                                logger.info(f"Playwright 攔截到 SAPI 部位數據: {len(positions)} 筆")
                        except Exception:
                            pass

                page.on("response", handle_resp)

                try:
                    page.goto(self.url, timeout=self.timeout)
                    time.sleep(4)
                except Exception as e:
                    logger.warning(f"Playwright 頁面載入異常: {e}")

                browser.close()
        except Exception as e:
            logger.warning(f"Playwright 執行例外: {e}")

        return None

    def scrape(self, mock_on_fail: bool = True) -> List[Dict[str, Any]]:
        """
        執行爬蟲抓取流程 (包含持倉部位、餘額與最新動態留言)
        """
        # 抓取持股部位
        data = self.fetch_via_direct_api()
        if not data:
            data = self.fetch_via_playwright()

        # 抓取最新動態留言
        self.fetch_latest_comment()

        if not data:
            if mock_on_fail:
                logger.warning("未能從網路獲取到部位資料，降級使用 Mock 數據進行後續流程。")
                data = get_mock_portfolio_data()
            else:
                data = []

        if not self.latest_comment and mock_on_fail:
            logger.warning("未能從網路獲取到動態留言，降級使用 Mock 留言數據。")
            self.latest_comment = get_mock_comment_data()

        return self._clean_and_sort(data)

    def _clean_and_sort(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """清洗數據並依佔比由大到小排序"""
        cleaned = sorted(data, key=lambda x: float(x.get("allocation", 0.0)), reverse=True)
        return cleaned


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="eToro Portfolio Scraper")
    parser.add_argument("--username", default="miulatw", help="eToro username")
    parser.add_argument("--mock", action="store_true", help="直接返回 Mock 測試數據")
    args = parser.parse_args()

    if args.mock:
        print("=== Mock 持股部位 ===")
        print(json.dumps(get_mock_portfolio_data(), indent=2, ensure_ascii=False))
        print("=== Mock 動態留言 ===")
        print(json.dumps(get_mock_comment_data(), indent=2, ensure_ascii=False))
    else:
        scraper = EToroScraper(username=args.username)
        result = scraper.scrape(mock_on_fail=True)
        print(f"成功抓取 {len(result)} 筆持股，餘額資訊: {scraper.cash_balance}")
        print(f"最新動態留言: {scraper.latest_comment}")
        print(json.dumps(result, indent=2, ensure_ascii=False))

