"""
eToro 追蹤系統配置模組 (Configuration)
定義追蹤之投資明星名單、各人物專屬網頁路徑與顯示資訊。
"""

from typing import List, Dict, Any, Optional

INVESTORS: List[Dict[str, Any]] = [
    {
        "username": "miulatw",
        "display_name": "Miula",
        "html_file": "index.html",
        "title": "Miula 投資組合追蹤",
        "description": "科技趨勢與美股宏觀投資",
        "avatar_url": "https://etoro-cdn.etorostatic.com/avatars/50X50/8220524/1.jpg"
    },
    {
        "username": "jeppekirkbonde",
        "display_name": "Jeppe Kirk Bonde",
        "html_file": "jeppekirkbonde.html",
        "title": "Jeppe Kirk Bonde 投資組合追蹤",
        "description": "全球宏觀與價值成長股組合",
        "avatar_url": "https://etoro-cdn.etorostatic.com/avatars/50X50/2988943/1.jpg"
    },
    {
        "username": "cphequities",
        "display_name": "CPH Equities",
        "html_file": "cphequities.html",
        "title": "CPH Equities 投資組合追蹤",
        "description": "歐洲與全球優質企業長線配置",
        "avatar_url": "https://etoro-cdn.etorostatic.com/avatars/50X50/6216244/1.jpg"
    }
]


def get_investor(username: str) -> Dict[str, Any]:
    """根據 username 取得投資者設定，若不在設定清單中則返回通用預設配置"""
    if not username:
        return INVESTORS[0]
    u_lower = username.lower()
    for inv in INVESTORS:
        if inv["username"].lower() == u_lower:
            return inv
    return {
        "username": username,
        "display_name": username,
        "html_file": f"{username}.html",
        "title": f"{username} 投資組合追蹤",
        "description": "eToro 明星投資者",
        "avatar_url": ""
    }


def get_all_investors() -> List[Dict[str, Any]]:
    """取得所有被追蹤的投資者清單"""
    return INVESTORS
